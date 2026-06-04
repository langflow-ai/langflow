"""stop() writes the durable STOP signal (the single source of truth, no fast-path)."""

from __future__ import annotations

import uuid

import fakeredis.aioredis as fakeredis_aio
import pytest
from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
from langflow.services.database.models.jobs.model import SignalType
from langflow.services.deps import get_job_service


@pytest.mark.usefixtures("client")
@pytest.mark.asyncio
async def test_stop_writes_durable_signal(active_user):
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid.uuid4(), user_id=active_user.id)

    redis = fakeredis_aio.FakeRedis()
    backend = RedisBackgroundQueue(client=redis, job_service=jobs)
    await backend.stop(str(job_id))

    # Source of truth: a STOP signal row a worker will see at the next boundary.
    signals = await jobs.unconsumed_signals(job_id)
    assert any(s.signal_type == SignalType.STOP for s in signals)


@pytest.mark.usefixtures("client")
@pytest.mark.asyncio
async def test_stop_writes_no_dead_pubsub_marker(active_user):
    """stop() must NOT set a cancel marker / publish: nothing in the worker reads it.

    The background worker does not run the v1 RedisJobQueueService cancel
    dispatcher, so a marker + PUBLISH would be a dead, misleading fast-path. The
    durable STOP signal is the only mechanism; assert no cancel marker is written.
    """
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid.uuid4(), user_id=active_user.id)

    redis = fakeredis_aio.FakeRedis()
    backend = RedisBackgroundQueue(client=redis, job_service=jobs)
    await backend.stop(str(job_id))

    marker = await redis.get(f"langflow:cancel-marker:{job_id}")
    assert marker is None, "stop() wrote a dead cancel marker no worker consumes"
