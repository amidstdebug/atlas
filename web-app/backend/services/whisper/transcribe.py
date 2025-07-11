import logging
from typing import Dict, Any, List
import requests
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from config.settings import get_settings
from models.TranscriptionResponse import TranscriptionSegment

logger = logging.getLogger(__name__)
settings = get_settings()

async def transcribe_audio_file(file_content: bytes, filename: str, content_type: str) -> List[TranscriptionSegment]:
    """
    Send audio file to Whisper service for transcription.
    """
    try:
        # Get Whisper service URL from settings
        whisper_service_url = settings.whisper_service_url

        # Prepare the file for the request
        files = {'file': (filename, file_content, content_type)}

        logger.info(f"Sending transcription request to Whisper service: {whisper_service_url}")

        # Make request to Whisper service
        response = await run_in_threadpool(
            lambda: requests.post(f"{whisper_service_url}/transcribe", files=files, timeout=300)
        )

        if response.status_code != 200:
            logger.error(f"Whisper service error: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Whisper service error: {response.text}"
            )

        # Parse the response
        result = response.json()
        segments_data = result.get('segments', [])

        # Convert to TranscriptionSegment objects
        segments = [
            TranscriptionSegment(
                text=seg['text'],
                start=float(seg['start']),
                end=float(seg['end'])
            )
            for seg in segments_data
        ]

        logger.info(f"Transcription completed: {len(segments)} segments")
        return segments

    except requests.exceptions.RequestException as e:
        logger.error(f"Request to Whisper service failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Whisper service unavailable: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error in transcribe_audio_file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}"
        )