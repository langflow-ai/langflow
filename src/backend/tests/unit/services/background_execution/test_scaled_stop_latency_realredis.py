"""Real-redis + real-DB: scaled stop latency is bounded by the vertex-boundary poll.

Scaled stop has NO pub/sub fast-path: the durable STOP signal is the source of
truth, and the worker's JobRunner polls ``unconsumed_signals`` at each durable
vertex/milestone boundary. This proves the latency contract: a job emitting a
durable frame every ``boundary_s`` is cancelled within a small number of
boundaries after ``stop_job`` (not "never" and not "one long vertex too late"),
so removing the dead fast-path did not regress responsiveness — the durable poll
delivers a bounded stop on its own.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import TYPE_CHECKING

import pytest
from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
from langflow.services.background_execution.redis_live_bus import RedisStreamLiveBus
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.background_execution.worker import WorkerJobRunner, run_worker_loop
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_job_service, get_settings_service

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.usefixtures("client")

_BOUNDARY_S = 0.1


def _frame(event_type: str, data: dict) -> tuple[bytes, str]:
    import json

    return (json.dumps({"event": event_type, "data": data}).encode("utf-8"), event_type)


def _cadence_source_factory(in_flight: asyncio.Event):
    def _factory(**_kw):
        async def _source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
            yield _frame("build_start", {})
            in_flight.set()
            # Durable frame every _BOUNDARY_S so the STOP poll fires on a known cadence.
            for i in range(200):
                await asyncio.sleep(_BOUNDARY_S)
                yield _frame("end_vertex", {"id": f"n{i}"})
            yield _frame("end", {})

        return _source

    return _factory


async def test_scaled_stop_latency_is_bounded(real_redis, active_user):
    jobs = get_job_service()
    settings = get_settings_service().settings
    settings.job_queue_type = "redis"
    prefix = real_redis._bgtest_prefix

    backend = RedisBackgroundQueue(client=real_redis, job_service=jobs, startup_grace_s=10.0)
    backend.claim_queue.pending_key = f"{prefix}pending"
    backend.claim_queue.processing_key = f"{prefix}processing"
    facade = BackgroundExecutionService(settings_service=get_settings_service(), backend=backend)

    job_id = await facade.submit(flow_id=uuid.uuid4(), request={"stream_protocol": "langflow"}, user=active_user)

    in_flight = asyncio.Event()
    live_bus = RedisStreamLiveBus(real_redis, ttl=60)
    worker_runner = WorkerJobRunner(
        settings=settings, live_bus=live_bus, frame_source_factory=_cadence_source_factory(in_flight)
    )
    stop_event = asyncio.Event()
    latency: dict[str, float] = {}

    async def drive_stop_then_wait():
        await asyncio.wait_for(in_flight.wait(), timeout=10.0)
        t0 = time.monotonic()
        await facade.stop_job(job_id, active_user)
        for _ in range(400):
            refreshed = await jobs.get_job_by_job_id(job_id)
            if refreshed.status in {JobStatus.CANCELLED, JobStatus.COMPLETED, JobStatus.FAILED}:
                latency["s"] = time.monotonic() - t0
                stop_event.set()
                return
            await asyncio.sleep(0.02)
        stop_event.set()

    driver = asyncio.create_task(drive_stop_then_wait())
    await run_worker_loop(backend, worker_runner, stop_event=stop_event, idle_block_ms=50)
    await driver

    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.CANCELLED
    # Bounded: cancelled within a few boundary polls, not "one long vertex" later.
    # 20 boundaries (2s) is a generous ceiling over the 0.1s cadence — a real
    # regression (stop never honored) would blow well past this.
    assert latency.get("s", 999) <= 20 * _BOUNDARY_S, f"stop latency unbounded: {latency}"
