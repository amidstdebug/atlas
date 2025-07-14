import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from services.summary import vllm_service

class DummyResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data or {}

    def json(self):
        return self._data


def test_call_vllm_success():
    payload = {"model": "test-model", "messages": [{"role": "user", "content": "hi"}]}

    mock_resp = DummyResponse(200, {"choices": [{"message": {"content": "ok"}}]})
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        result = asyncio.run(vllm_service._call_vllm(payload))
    assert result["choices"][0]["message"]["content"] == "ok"


def test_generate_completion_uses_queue():
    payload = {"some": "data"}

    class DummyQueue:
        def __init__(self):
            self.enqueued = []
        async def enqueue(self, data):
            self.enqueued.append(data)
            return "job1"
        async def await_result(self, job_id):
            return {"done": True}

    dummy = DummyQueue()
    with patch.object(vllm_service, "queue", dummy):
        result = asyncio.run(vllm_service.generate_completion(payload))
    assert dummy.enqueued[0] == payload
    assert result == {"done": True}

