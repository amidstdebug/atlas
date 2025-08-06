import logging
import base64
from typing import List, Optional
import requests
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from config.settings import get_settings, settings
from models.TranscriptionResponse import TranscriptionSegment
from services.queue.redis_queue import RedisQueue

logger = logging.getLogger(__name__)
settings = get_settings()
queue = RedisQueue("whisper_tasks", settings.redis_url)


async def _send_to_whisper(
    file_content: bytes,
    filename: str,
    content_type: str,
    prompt: Optional[str] = None,
) -> List[TranscriptionSegment]:
    """Directly send audio file to the Whisper service."""
    whisper_service_url = settings.whisper_service_url
    files = {"file": (filename, file_content, content_type)}
    data = {"prompt": prompt} if prompt else {}
    logger.info(f"Sending transcription request to Whisper service: {whisper_service_url}")
    response = await run_in_threadpool(
        lambda: requests.post(
            f"{whisper_service_url}/transcribe",
            files=files,
            data=data,
            timeout=300,
        )
    )
    if response.status_code != 200:
        logger.error(f"Whisper service error: {response.status_code} - {response.text}")
        raise HTTPException(status_code=response.status_code, detail=f"Whisper service error: {response.text}")

    result = response.json()
    segments_data = result.get("segments", [])
    return [TranscriptionSegment(text=seg["text"], start=float(seg["start"]), end=float(seg["end"])) for seg in segments_data]

async def transcribe_audio_file(
    file_content: bytes,
    filename: str,
    content_type: str,
    prompt: Optional[str] = None,
) -> List[TranscriptionSegment]:
    """Queue the transcription request and wait for the result."""
    try:
        encoded = base64.b64encode(file_content).decode("utf-8")
        job_id = await queue.enqueue({
            "file_content": encoded,
            "filename": filename,
            "content_type": content_type,
            # "prompt": prompt,
        })
        result = await queue.await_result(job_id)
        if isinstance(result, dict) and result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])
        return [TranscriptionSegment(**seg) for seg in result]
    except Exception as e:
        logger.error(f"Error in transcribe_audio_file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")



