"""Scaled lease-aware reconcile + periodic watchdog (real redis + real DB).

These prove the at-most-once guarantee for the scaled backend:

* A booting worker B's requeue_lost must NOT reclaim / fail a job whose lease is
  still FRESH (a live worker A is running it) — no double-run, no phantom fail.
* A dead worker's in-flight job (stale lease) IS reconciled by the PERIODIC
  watchdog WITHOUT any new worker process starting.
* Concurrent reconcilers race a single lost retry-safe job at most once more
  (atomic attempt accounting), never exceeding max_attempts.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

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


async def test_requeue_lost_spares_fresh_lease_in_progress(real_redis, active_user):
    """A live IN_PROGRESS job (fresh heartbeat) is left alone by requeue_lost."""
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid.uuid4(), user_id=active_user.id)
    await jobs.update_job_status(job_id, JobStatus.IN_PROGRESS)
    await jobs.heartbeat(job_id, owner="worker-A")  # live worker A is running it

    backend = _scoped_backend(real_redis, jobs)
    # The id is on the processing list (worker A claimed it) and A is still running.
    await real_redis.lpush(backend.claim_queue.processing_key, str(job_id))

    # Worker B boots and reconciles. A's lease is fresh -> B must NOT touch it.
    requeued = await backend.requeue_lost(lease_ttl_s=30.0)
    assert str(job_id) not in requeued

    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.IN_PROGRESS  # not failed, not requeued
    pending = await real_redis.lrange(backend.claim_queue.pending_key, 0, -1)
    assert str(job_id).encode() not in pending  # not double-enqueued
    # Still on processing (A owns it).
    assert str(job_id) in await backend.claim_queue.processing_ids()


async def test_requeue_lost_spares_fresh_lease_queued(real_redis, active_user):
    """A QUEUED job a live worker JUST claimed (fresh heartbeat) is not re-claimed."""
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid.uuid4(), user_id=active_user.id)
    # Worker A claimed it and stamped a heartbeat-on-claim, but has not yet
    # flipped it to IN_PROGRESS (the QUEUED->IN_PROGRESS window).
    await jobs.heartbeat(job_id, owner="worker-A")

    backend = _scoped_backend(real_redis, jobs)
    await real_redis.lpush(backend.claim_queue.processing_key, str(job_id))

    requeued = await backend.requeue_lost(lease_ttl_s=30.0)
    assert str(job_id) not in requeued
    pending = await real_redis.lrange(backend.claim_queue.pending_key, 0, -1)
    assert str(job_id).encode() not in pending


async def test_requeue_lost_reconciles_stale_lease_in_progress(real_redis, active_user):
    """A dead worker's IN_PROGRESS job (stale lease) is failed worker_lost."""
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid.uuid4(), user_id=active_user.id)
    await jobs.update_job_status(job_id, JobStatus.IN_PROGRESS)
    old = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    await jobs.update_job_metadata(job_id, {"owner": "dead-worker", "heartbeat_at": old})

    backend = _scoped_backend(real_redis, jobs)
    await real_redis.lpush(backend.claim_queue.processing_key, str(job_id))

    await backend.requeue_lost(lease_ttl_s=30.0)
    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.FAILED
    assert (refreshed.error or {}).get("type") == "worker_lost"
    assert str(job_id) not in await backend.claim_queue.processing_ids()


async def test_concurrent_reconcile_caps_attempts(real_redis, active_user):
    """Two reconcilers racing one stale retry-safe job bump attempt only once."""
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid.uuid4(), user_id=active_user.id)
    await jobs.update_job_status(job_id, JobStatus.IN_PROGRESS)
    old = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    await jobs.update_job_metadata(
        job_id,
        {"retry_safe": True, "max_attempts": 5, "attempt": 1, "owner": "dead", "heartbeat_at": old},
    )

    backend = _scoped_backend(real_redis, jobs)
    await real_redis.lpush(backend.claim_queue.processing_key, str(job_id))

    # Race many reconcilers against the single lost job.
    results = await asyncio.gather(*(backend.requeue_lost(lease_ttl_s=30.0) for _ in range(8)))
    total_requeued = sum(str(job_id) in r for r in results)
    assert total_requeued == 1  # requeued exactly once, not 8 times

    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.job_metadata["attempt"] == 2  # bumped exactly once
    assert refreshed.status == JobStatus.QUEUED
    pending = await real_redis.lrange(backend.claim_queue.pending_key, 0, -1)
    assert pending.count(str(job_id).encode()) == 1  # one pending entry, no duplicates

    # No double-run: draining the queue yields the job exactly once more.
    first = await backend.claim(block_ms=200)
    second = await backend.claim(block_ms=200)
    assert first == str(job_id)
    assert second is None  # not claimable a second time -> runs at most once more


async def test_concurrent_reconcile_no_double_run_side_effect(real_redis, active_user):
    """A side-effect-style counter: concurrent reconcile of one lost job runs it once more.

    Models the at-most-once-for-retry guarantee with an observable counter: each
    time the reconciled job is CLAIMED off the queue counts as one (re)run. Many
    reconcilers racing the single lost id must leave the job claimable exactly
    once, so a draining worker would execute the side effect a single extra time.
    """
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid.uuid4(), user_id=active_user.id)
    await jobs.update_job_status(job_id, JobStatus.IN_PROGRESS)
    old = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    await jobs.update_job_metadata(
        job_id,
        {"retry_safe": True, "max_attempts": 10, "attempt": 1, "owner": "dead", "heartbeat_at": old},
    )

    backend = _scoped_backend(real_redis, jobs)
    await real_redis.lpush(backend.claim_queue.processing_key, str(job_id))

    await asyncio.gather(*(backend.requeue_lost(lease_ttl_s=30.0) for _ in range(12)))

    # Count how many times the job is claimable = how many times it would re-run.
    runs = 0
    while True:
        claimed = await backend.claim(block_ms=200)
        if claimed is None:
            break
        runs += 1
        assert claimed == str(job_id)
    assert runs == 1  # exactly one extra run, never two — no double side effect
