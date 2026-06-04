"""stop() writes the durable STOP signal (source of truth) and publishes the fast-path."""

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
async def test_stop_publishes_fastpath_marker(active_user):
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid.uuid4(), user_id=active_user.id)

    redis = fakeredis_aio.FakeRedis()
    backend = RedisBackgroundQueue(client=redis, job_service=jobs)
    await backend.stop(str(job_id))

    # Fast-path: the cancel marker is set so a worker that races the publish
    # still sees it on its start_job marker check.
    marker = await redis.get(f"langflow:cancel-marker:{job_id}")
    assert marker is not None
