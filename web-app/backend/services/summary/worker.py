import asyncio
import logging

from services.queue.redis_queue import RedisQueue
from .vllm_service import _call_vllm
from config.settings import settings

logger = logging.getLogger(__name__)
queue = RedisQueue("summary_tasks", settings.redis_url)


async def main() -> None:
    while True:
        job = await queue.dequeue()
        data = job["data"]
        try:
            result = await _call_vllm(data)
            await queue.send_result(job["id"], result)
        except Exception as e:
            logger.error(f"Summary worker error: {e}")
            await queue.send_result(job["id"], {"error": str(e)})


if __name__ == "__main__":
    asyncio.run(main())

