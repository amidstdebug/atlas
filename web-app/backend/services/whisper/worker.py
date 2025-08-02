import asyncio
import base64
import logging

from services.queue.redis_queue import RedisQueue
from .transcribe import _send_to_whisper
from config.settings import settings

logger = logging.getLogger(__name__)
queue = RedisQueue("whisper_tasks", settings.redis_url)


async def main() -> None:
    while True:
        job = await queue.dequeue()
        data = job["data"]
        try:
            content = base64.b64decode(data["file_content"])
            segments = await _send_to_whisper(
                content,
                data["filename"],
                data["content_type"],
                data.get("prompt"),
            )
            await queue.send_result(job["id"], [seg.dict() for seg in segments])
        except Exception as e:
            logger.error(f"Whisper worker error: {e}")
            await queue.send_result(job["id"], {"error": str(e)})


if __name__ == "__main__":
    asyncio.run(main())

