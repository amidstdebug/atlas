from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form
from fastapi.websockets import WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional
import json
import logging

from models.AuthType import TokenData
from models.TranscriptionResponse import TranscriptionResponse
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
        transcription_result = await transcribe_audio_file(file_content, file.filename, file.content_type)
        print("Transcription Result:", transcription_result)

        # Handle the transcription result structure
        transcription_data = transcription_result.get("transcription", transcription_result)

        if isinstance(transcription_data, dict) and "chunks" in transcription_data:
            transcription_segments = transcription_data["chunks"]
            transcription_text = transcription_data.get("text", " ".join([s.get("text", "").strip() for s in transcription_segments]))
        elif isinstance(transcription_data, list):
            transcription_segments = transcription_data
            transcription_text = " ".join([segment.get("text", "").strip() for segment in transcription_segments])
        else:
            # Fallback - log the actual structure for debugging
            logger.error(f"Unexpected transcription result structure: {type(transcription_result)}, {transcription_result}")
            raise HTTPException(status_code=500, detail="Unexpected transcription result structure")

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
                    # Create a single segment with the processed text
                    transcription_segments = [{"text": processed_text, "timestamp": [0.0, len(processed_text)]}]

                logger.info(f"Applied text processing to transcription - Numbers: {replace_numbers}, ICAO: {use_icao_callsigns}")
            except Exception as e:
                logger.warning(f"Text processing failed: {str(e)}. Using original transcription.")

        # Store the transcription in history for this user
        user_id = token_data.user_id
        if user_id not in transcription_history:
            transcription_history[user_id] = []

        transcription_history[user_id].append(transcription_text)

        return TranscriptionResponse(
            transcription=transcription_segments,
            processing_applied=processing_applied
        )

    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")