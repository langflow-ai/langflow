"""Real-redis + real-DB: facade stop_job (scaled) lands a STOP the worker honors -> CANCELLED.

The facade's scaled stop_job writes the durable ExecutionSignal(STOP), the single
source of truth (no pub/sub fast-path). The worker's JobRunner polls
unconsumed_signals at vertex boundaries and cooperatively cancels. This proves the
control path end-to-end on real redis: stop -> worker sees STOP -> job CANCELLED,
with the STOP signal stamped consumed.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import TYPE_CHECKING

import pytest
from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
from langflow.services.background_execution.redis_live_bus import RedisStreamLiveBus
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.background_execution.worker import WorkerJobRunner, run_worker_loop
from langflow.services.database.models.jobs.model import JobStatus, SignalType
from langflow.services.deps import get_job_service, get_settings_service

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.usefixtures("client")


def _frame(event_type: str, data: dict) -> tuple[bytes, str]:
    return (json.dumps({"event": event_type, "data": data}).encode("utf-8"), event_type)


def _slow_source_factory(stop_requested: asyncio.Event):
    # A frame-source factory is a plain callable returning an async-generator
    # callable (see _default_frame_source_factory) — NOT an async function.
    def _factory(**_kw):
        async def _source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
            # Emit a durable frame, signal the test that the run is in-flight, then
            # keep emitting durable frames slowly so the JobRunner polls the STOP
            # signal at a boundary and cancels before the natural end.
            yield _frame("build_start", {})
            stop_requested.set()
            for i in range(50):
                await asyncio.sleep(0.1)
                yield _frame("end_vertex", {"id": f"n{i}"})
            yield _frame("end", {})

        return _source

    return _factory


async def test_scaled_stop_cancels_the_running_job(real_redis, active_user):
    jobs = get_job_service()
    settings = get_settings_service().settings
    settings.job_queue_type = "redis"
    prefix = real_redis._bgtest_prefix

    backend = RedisBackgroundQueue(client=real_redis, job_service=jobs, startup_grace_s=10.0)
    backend.claim_queue.pending_key = f"{prefix}pending"
    backend.claim_queue.processing_key = f"{prefix}processing"
    facade = BackgroundExecutionService(settings_service=get_settings_service(), backend=backend)

    flow_id = uuid.uuid4()
    job_id = await facade.submit(flow_id=flow_id, request={"stream_protocol": "langflow"}, user=active_user)

    in_flight = asyncio.Event()
    live_bus = RedisStreamLiveBus(real_redis, ttl=60)
    worker_runner = WorkerJobRunner(
        settings=settings,
        live_bus=live_bus,
        frame_source_factory=_slow_source_factory(in_flight),
    )
    stop_event = asyncio.Event()

    async def drive_stop_then_wait():
        # Wait until the run is in-flight, then stop it through the facade.
        await asyncio.wait_for(in_flight.wait(), timeout=10.0)
        await facade.stop_job(job_id, active_user)
        # Wait until the durable row reaches CANCELLED, then end the worker loop.
        for _ in range(200):
            refreshed = await jobs.get_job_by_job_id(job_id)
            if refreshed.status in {JobStatus.CANCELLED, JobStatus.COMPLETED, JobStatus.FAILED}:
                stop_event.set()
                return
            await asyncio.sleep(0.05)
        stop_event.set()

    driver = asyncio.create_task(drive_stop_then_wait())
    await run_worker_loop(backend, worker_runner, stop_event=stop_event, idle_block_ms=50)
    await driver

    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.CANCELLED
    # The STOP signal was stamped consumed by the runner's terminal reconcile.
    leftover = [s for s in await jobs.unconsumed_signals(job_id) if s.signal_type == SignalType.STOP]
    assert leftover == []
