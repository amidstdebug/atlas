from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form
from typing import Dict, List, Optional
import json
import logging
import asyncio
import httpx

from models.AuthType import TokenData
from models.TranscriptionResponse import TranscriptionResponse, TranscriptionSegment
from services.auth.jwt import get_token_data
from services.whisper.transcribe import transcribe_audio_file

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Transcription"])

# Store transcription history
transcription_history = {}


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    prompt: Optional[str] = Form(None),
    token_data: TokenData = Depends(get_token_data)
):
    """Transcribe audio from an uploaded file"""
    try:
        # Read file content
        file_content = await file.read()

        # Call the transcription service with optional prompt
        segments = await transcribe_audio_file(
            file_content,
            file.filename,
            file.content_type,
            prompt,
        )
        print("Transcription Segments:", segments)

        # Extract text for processing
        transcription_text = " ".join([segment.text.strip() for segment in segments])

        # Store the transcription in history for this user
        user_id = token_data.user_id
        if user_id not in transcription_history:
            transcription_history[user_id] = []

        transcription_history[user_id].append(transcription_text)

        return TranscriptionResponse(
            segments=segments,
            processing_applied=None
        )

    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

