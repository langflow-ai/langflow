"""Real-redis + real-DB end-to-end: facade submit (scaled) -> worker runs -> COMPLETED.

This is the integration capstone. A scaled-mode facade submits a job (which only
enqueues onto the redis claim queue — no in-process execution), a worker loop
claims it and runs the real JobRunner via WorkerJobRunner with a scripted frame
source (no LLM), and the durable job row reaches COMPLETED with a replayable
event log. A SECOND facade instance (a different API replica) then reattaches and
replays the durable milestones — cross-replica, no gap.

Uses real redis (LANGFLOW_TEST_REDIS_URL) + the migrated test DB. No mocks of our
code: the only injected piece is the scripted frame source standing in for a live
graph build (same pattern as test_service.py).
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
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_job_service, get_settings_service
from langflow.services.job_queue.service import _STREAM_PREFIX

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.usefixtures("client")


def _frame(event_type: str, data: dict) -> tuple[bytes, str]:
    return (json.dumps({"event": event_type, "data": data}).encode("utf-8"), event_type)


async def _scripted_source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
    yield _frame("build_start", {})
    yield _frame("end_vertex", {"id": "n1"})
    yield _frame("end", {})


def _scaled_settings():
    settings = get_settings_service().settings
    # Force scaled selection for this facade instance without touching global env.
    settings.job_queue_type = "redis"
    return settings


async def test_submit_then_worker_runs_to_completion(real_redis, real_redis_url, active_user):
    from redis.asyncio import StrictRedis

    jobs = get_job_service()
    settings = _scaled_settings()
    prefix = real_redis._bgtest_prefix

    # API replica A: scaled facade wired to the real redis backend.
    backend_a = RedisBackgroundQueue(client=real_redis, job_service=jobs, startup_grace_s=10.0)
    backend_a.claim_queue.pending_key = f"{prefix}pending"
    backend_a.claim_queue.processing_key = f"{prefix}processing"
    facade_a = BackgroundExecutionService(settings_service=get_settings_service(), backend=backend_a)

    flow_id = uuid.uuid4()
    job_id = await facade_a.submit(flow_id=flow_id, request={"stream_protocol": "langflow"}, user=active_user)

    # In scaled mode the API process must NOT execute — the job sits QUEUED on the
    # claim queue until a worker picks it up.
    queued = await jobs.get_job_by_job_id(job_id)
    assert queued.status == JobStatus.QUEUED
    pending = await real_redis.lrange(backend_a.claim_queue.pending_key, 0, -1)
    assert str(job_id).encode() in pending

    # Worker process (separate task): claim + run the real JobRunner with a
    # scripted source, publishing live frames to redis Streams.
    live_bus = RedisStreamLiveBus(real_redis, ttl=60)
    worker_runner = WorkerJobRunner(
        settings=settings,
        live_bus=live_bus,
        frame_source_factory=lambda **_kw: _scripted_source,
    )
    stop_event = asyncio.Event()

    async def stop_when_done():
        for _ in range(200):
            refreshed = await jobs.get_job_by_job_id(job_id)
            if refreshed.status == JobStatus.COMPLETED:
                stop_event.set()
                return
            await asyncio.sleep(0.05)
        stop_event.set()

    driver = asyncio.create_task(stop_when_done())
    await run_worker_loop(backend_a, worker_runner, stop_event=stop_event, idle_block_ms=50)
    await driver

    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.COMPLETED
    assert refreshed.result is not None
    # Lease released.
    assert str(job_id) not in await backend_a.claim_queue.processing_ids()

    # API replica B: a different facade instance on a SEPARATE connection that
    # never ran the job reattaches and replays the durable milestones.
    client_b = StrictRedis.from_url(real_redis_url)
    backend_b = RedisBackgroundQueue(client=client_b, job_service=jobs, stream_ttl=60, startup_grace_s=10.0)
    facade_b = BackgroundExecutionService(settings_service=get_settings_service(), backend=backend_b)
    try:
        seen = [chunk async for chunk in facade_b.events(job_id, last_event_id=None, user=active_user)]
    finally:
        await client_b.aclose()
        await real_redis.delete(f"{_STREAM_PREFIX}{job_id}")

    assert any(b"build_start" in c for c in seen)
    assert any(b"end_vertex" in c for c in seen)
