"""Real-redis + real-DB: a worker that claims then dies is reconciled by the watchdog.

Proves the lease-recovery path against REAL redis (real BRPOPLPUSH claim leaving
the id on a real processing list) + the real DB job row, not a simulated lpush.
A QUEUED job whose claimant died is requeued (at-least-once); an IN_PROGRESS job
whose claimant died is failed worker_lost by default (at-most-once); a retry-safe
IN_PROGRESS job is requeued with a bumped attempt up to max_attempts.
"""

from __future__ import annotations

import uuid

import pytest
from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_job_service

pytestmark = pytest.mark.usefixtures("client")


def _scoped_backend(real_redis, jobs):
    prefix = real_redis._bgtest_prefix
    backend = RedisBackgroundQueue(client=real_redis, job_service=jobs, startup_grace_s=10.0)
    backend.claim_queue.pending_key = f"{prefix}pending"
    backend.claim_queue.processing_key = f"{prefix}processing"
    return backend


async def test_real_claimed_then_dead_queued_job_is_requeued(real_redis, active_user):
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid.uuid4(), user_id=active_user.id)

    backend = _scoped_backend(real_redis, jobs)
    await backend.enqueue(str(job_id))

    # A real worker claims the job (real BRPOPLPUSH move to the processing list)
    # and then "crashes" — it never calls complete(), so the id is stranded.
    claimed = await backend.claim(block_ms=1000)
    assert claimed == str(job_id)
    assert str(job_id) in await backend.claim_queue.processing_ids()

    # Watchdog reconciles: the job never left QUEUED, so requeue it for re-claim.
    requeued = await backend.requeue_lost()
    assert str(job_id) in requeued
    pending = await real_redis.lrange(backend.claim_queue.pending_key, 0, -1)
    assert str(job_id).encode() in pending
    assert str(job_id) not in await backend.claim_queue.processing_ids()


async def test_real_claimed_then_dead_in_progress_job_fails_worker_lost(real_redis, active_user):
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid.uuid4(), user_id=active_user.id)

    backend = _scoped_backend(real_redis, jobs)
    await backend.enqueue(str(job_id))
    claimed = await backend.claim(block_ms=1000)
    assert claimed == str(job_id)
    # The worker started the job (IN_PROGRESS) and then died mid-flight.
    await jobs.update_job_status(job_id, JobStatus.IN_PROGRESS)

    await backend.requeue_lost()

    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.FAILED
    assert (refreshed.error or {}).get("type") == "worker_lost"
    # Not requeued (at-most-once default) and the lease is released.
    pending = await real_redis.lrange(backend.claim_queue.pending_key, 0, -1)
    assert str(job_id).encode() not in pending
    assert str(job_id) not in await backend.claim_queue.processing_ids()


async def test_real_retry_safe_in_progress_requeues_until_max(real_redis, active_user):
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid.uuid4(), user_id=active_user.id)
    await jobs.update_job_status(job_id, JobStatus.IN_PROGRESS)
    await jobs.update_job_metadata(job_id, {"retry_safe": True, "max_attempts": 2, "attempt": 1})

    backend = _scoped_backend(real_redis, jobs)
    await backend.enqueue(str(job_id))
    await backend.claim(block_ms=1000)

    # First death: retry-safe + attempt < max => requeued, attempt bumped, QUEUED.
    requeued = await backend.requeue_lost()
    assert str(job_id) in requeued
    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.QUEUED
    assert refreshed.job_metadata["attempt"] == 2

    # Re-claim, go IN_PROGRESS, die again at the attempt cap => FAILED worker_lost.
    await backend.claim(block_ms=1000)
    await jobs.update_job_status(job_id, JobStatus.IN_PROGRESS)
    await backend.requeue_lost()
    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.FAILED
    assert (refreshed.error or {}).get("type") == "worker_lost"
