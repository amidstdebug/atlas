import asyncio
import logging

from services.queue.redis_queue import RedisQueue
from .gemini_service import _call_gemini
from config.settings import settings

logger = logging.getLogger(__name__)
queue = RedisQueue("summary_tasks", settings.redis_url)

async def main() -> None:
    """Worker for processing summary tasks via Redis queue (optional/legacy)"""
    logger.info("Starting summary worker with OpenAI-compatible Gemini service")
    
    while True:
        try:
            job = await queue.dequeue()
            data = job["data"]
            
            logger.info(f"Processing summary job: {job['id']}")
            result = await _call_gemini(data)
            await queue.send_result(job["id"], result)
            
        except Exception as e:
            logger.error(f"Summary worker error: {e}")
            await queue.send_result(job["id"], {"error": str(e)})

if __name__ == "__main__":
    asyncio.run(main())

