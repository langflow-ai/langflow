"""build_worker wires the DB backend + WorkerJobRunner from live services."""

from __future__ import annotations

import pytest
from langflow.services.background_execution.db_backend import DBBackgroundQueue
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.worker import WorkerJobRunner, build_worker
from langflow.services.deps import get_job_service

pytestmark = pytest.mark.usefixtures("client")


async def test_build_worker_returns_backend_runner_and_teardown():
    backend, runner, teardown = await build_worker(owner="worker:test")
    try:
        assert isinstance(backend, DBBackgroundQueue)
        assert isinstance(runner, WorkerJobRunner)
        assert callable(teardown)
        # The backend claims off the live job service (the shared database is
        # the queue), and the runner's bus is process-local — durable milestones
        # in job_events are the cross-replica transport.
        assert backend._job_service is get_job_service()
        assert isinstance(runner._live_bus, InMemoryLiveBus)
        assert backend._owner == "worker:test"
    finally:
        await teardown()
