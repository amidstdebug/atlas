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
    Send audio file to audio service for transcription.
    """
    try:
        # Forward the file to the audio_service
        files = {'file': (filename, file_content, content_type)}
        audio_service_url = f"{settings.audio_server_url}/transcribe"

        response = await run_in_threadpool(
            lambda: requests.post(audio_service_url, files=files)
        )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code,
                            detail=f"Audio service error: {response.text}")

        # Get the transcription from audio_service
        result = response.json()
        segments_data = result['segments']
        
        segments = [
            TranscriptionSegment(
                text=seg['text'],
                start=float(seg['start']),
                end=float(seg['end'])
            )
            for seg in segments_data
        ]

        return segments

    except Exception as e:
        logger.error(f"Error in transcribe_audio_file: {str(e)}")
        raise