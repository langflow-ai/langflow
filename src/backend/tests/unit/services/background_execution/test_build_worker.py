"""build_worker wires the redis backend + WorkerJobRunner from live services."""

from __future__ import annotations

import pytest
from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
from langflow.services.background_execution.worker import WorkerJobRunner, build_worker

pytestmark = pytest.mark.usefixtures("client")


async def test_build_worker_returns_backend_runner_and_teardown():
    backend, runner, teardown = await build_worker()
    try:
        assert isinstance(backend, RedisBackgroundQueue)
        assert isinstance(runner, WorkerJobRunner)
        assert callable(teardown)
        # The backend's claim queue and the runner's live bus share one client.
        assert backend._client is runner._live_bus._client
    finally:
        await teardown()
