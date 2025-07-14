import asyncio
import json
import uuid
from typing import Any, Dict

import redis.asyncio as redis

class RedisQueue:
    """Simple FIFO queue backed by Redis."""

    def __init__(self, name: str, redis_url: str):
        self.name = name
        self.redis = redis.from_url(redis_url, decode_responses=True)

    async def enqueue(self, data: Dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        job = {"id": job_id, "data": data}
        await self.redis.rpush(self.name, json.dumps(job))
        return job_id

    async def dequeue(self, timeout: int = 0) -> Dict[str, Any]:
        _, raw = await self.redis.blpop(self.name, timeout=timeout)
        return json.loads(raw)

    async def send_result(self, job_id: str, result: Any) -> None:
        await self.redis.rpush(f"{self.name}:{job_id}:result", json.dumps(result))

    async def await_result(self, job_id: str, timeout: int = 0) -> Any:
        key = f"{self.name}:{job_id}:result"
        _, raw = await self.redis.blpop(key, timeout=timeout)
        await self.redis.delete(key)
        return json.loads(raw)
