"""Lease watchdog: QUEUED requeues; IN_PROGRESS fails worker_lost; retry-safe requeues to max."""

from __future__ import annotations

import uuid

import fakeredis.aioredis as fakeredis_aio
import pytest
from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_job_service


async def _make_job(flow_id, *, status, user_id, metadata=None):
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)
    if status != JobStatus.QUEUED:
        await jobs.update_job_status(job_id, status)
    if metadata:
        await jobs.update_job_metadata(job_id, metadata)
    return jobs, job_id


@pytest.mark.usefixtures("client")
@pytest.mark.asyncio
async def test_queued_lost_job_is_requeued(active_user):
    flow_id = uuid.uuid4()
    jobs, job_id = await _make_job(flow_id, status=JobStatus.QUEUED, user_id=active_user.id)

    redis = fakeredis_aio.FakeRedis()
    backend = RedisBackgroundQueue(client=redis, job_service=jobs)
    # Simulate a claimed-but-orphaned id on the processing list.
    await redis.lpush(backend.claim_queue.processing_key, str(job_id))

    requeued = await backend.requeue_lost()
    assert str(job_id) in requeued
    pending = await redis.lrange(backend.claim_queue.pending_key, 0, -1)
    assert str(job_id).encode() in pending


@pytest.mark.usefixtures("client")
@pytest.mark.asyncio
async def test_in_progress_lost_job_fails_worker_lost(active_user):
    flow_id = uuid.uuid4()
    jobs, job_id = await _make_job(flow_id, status=JobStatus.IN_PROGRESS, user_id=active_user.id)

    redis = fakeredis_aio.FakeRedis()
    backend = RedisBackgroundQueue(client=redis, job_service=jobs)
    await redis.lpush(backend.claim_queue.processing_key, str(job_id))

    await backend.requeue_lost()

    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.FAILED
    # set_error stores {"type": "worker_lost"} on the durable job.error column.
    err = refreshed.error or {}
    assert err.get("type") == "worker_lost"
    # Not requeued.
    pending = await redis.lrange(backend.claim_queue.pending_key, 0, -1)
    assert str(job_id).encode() not in pending


@pytest.mark.usefixtures("client")
@pytest.mark.asyncio
async def test_retry_safe_in_progress_requeues_until_max(active_user):
    flow_id = uuid.uuid4()
    jobs, job_id = await _make_job(
        flow_id,
        status=JobStatus.IN_PROGRESS,
        user_id=active_user.id,
        metadata={"retry_safe": True, "max_attempts": 2, "attempt": 1},
    )

    redis = fakeredis_aio.FakeRedis()
    backend = RedisBackgroundQueue(client=redis, job_service=jobs)
    await redis.lpush(backend.claim_queue.processing_key, str(job_id))

    requeued = await backend.requeue_lost()
    assert str(job_id) in requeued
    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.QUEUED
    assert refreshed.job_metadata["attempt"] == 2


@pytest.mark.usefixtures("client")
@pytest.mark.asyncio
async def test_retry_safe_exhausted_fails(active_user):
    flow_id = uuid.uuid4()
    jobs, job_id = await _make_job(
        flow_id,
        status=JobStatus.IN_PROGRESS,
        user_id=active_user.id,
        metadata={"retry_safe": True, "max_attempts": 2, "attempt": 2},
    )

    redis = fakeredis_aio.FakeRedis()
    backend = RedisBackgroundQueue(client=redis, job_service=jobs)
    await redis.lpush(backend.claim_queue.processing_key, str(job_id))

    await backend.requeue_lost()
    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.FAILED
    err = refreshed.error or {}
    assert err.get("type") == "worker_lost"
