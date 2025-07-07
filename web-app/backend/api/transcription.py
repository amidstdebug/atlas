from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form
from fastapi.websockets import WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional
import json
import logging
import asyncio
import httpx
import websockets

from models.AuthType import TokenData
from models.TranscriptionResponse import TranscriptionResponse, TranscriptionSegment
from services.auth.jwt import get_token_data
from services.whisper.transcribe import transcribe_audio_file
from services.whisper.text_processor import process_transcription_text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Transcription"])

# Store connected clients and their latest transcriptions
connected_clients = {}
transcription_history = {}


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    replace_numbers: bool = Form(True),
    use_icao_callsigns: bool = Form(True),
    token_data: TokenData = Depends(get_token_data)
):
    """Transcribe audio from an uploaded file with optional text processing"""
    try:
        # Read file content
        file_content = await file.read()

        # Call the transcription service
        segments = await transcribe_audio_file(file_content, file.filename, file.content_type)
        print("Transcription Segments:", segments)

        # Extract text for processing
        transcription_text = " ".join([segment.text.strip() for segment in segments])

        # Apply text processing if requested
        processing_applied = None
        if replace_numbers or use_icao_callsigns:
            try:
                processing_result = await process_transcription_text(
                    transcription_text,
                    replace_numbers,
                    use_icao_callsigns
                )
                # Get the processed text
                processed_text = processing_result["processed_text"]
                processing_applied = processing_result["replacements_applied"]

                # If text was actually processed (changed), update segments with processed text
                if processed_text != transcription_text:
                    # Create a single segment with the processed text, preserving timing from original segments
                    start_time = segments[0].start if segments else 0.0
                    end_time = segments[-1].end if segments else 0.0
                    segments = [TranscriptionSegment(text=processed_text, start=start_time, end=end_time)]

                logger.info(f"Applied text processing to transcription - Numbers: {replace_numbers}, ICAO: {use_icao_callsigns}")
            except Exception as e:
                logger.warning(f"Text processing failed: {str(e)}. Using original transcription.")

        # Store the transcription in history for this user
        user_id = token_data.user_id
        if user_id not in transcription_history:
            transcription_history[user_id] = []

        transcription_history[user_id].append(transcription_text)

        return TranscriptionResponse(
            segments=segments,
            processing_applied=processing_applied
        )

    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@router.websocket("/ws/live-transcribe")
async def websocket_live_transcribe(websocket: WebSocket):
    """WebSocket endpoint for live audio transcription (proxy to Whisper)"""
    # extract token from query string
    token = websocket.query_params.get("token")
    # accept the websocket handshake first
    await websocket.accept()

    if not token:
        await websocket.close(code=1008, reason="No token provided")
        return

    try:
        import jwt
        from config.settings import get_settings
        settings = get_settings()
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("user_id")
    except jwt.ExpiredSignatureError:
        await websocket.close(code=1008, reason="Token has expired")
        return
    except jwt.InvalidTokenError:
        await websocket.close(code=1008, reason="Invalid token")
        return

    # now proxy to whisper-livekit
    try:
        async with websockets.connect("ws://whisper_livekit:8000/asr") as proxy_ws:
            async def forward_client_to_proxy():
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        await proxy_ws.send(data)
                except WebSocketDisconnect:
                    await proxy_ws.close()

            async def forward_proxy_to_client():
                try:
                    async for msg in proxy_ws:
                        if isinstance(msg, bytes):
                            await websocket.send_bytes(msg)
                        else:
                            await websocket.send_text(msg)
                except Exception:
                    await websocket.close()

            await asyncio.gather(
                forward_client_to_proxy(),
                forward_proxy_to_client(),
            )
    except Exception as e:
        logger.error(f"WebSocket proxy error for user {user_id}: {e}")
        await websocket.close(code=1011, reason="Proxy error")