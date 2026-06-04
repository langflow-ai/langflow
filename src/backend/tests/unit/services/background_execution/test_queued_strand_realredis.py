"""Scaled recovery of a QUEUED job stranded off the redis lists (real redis + DB).

If the API crashes between persisting a QUEUED row and the enqueue LPUSH (or
redis loses the pending list), the DB row is QUEUED but on NEITHER redis list.
requeue_lost only scans the processing list, so without a dedicated recover the
job is stuck QUEUED forever. recover_stranded_queued re-enqueues it; a row that
IS already on a redis list must not be double-enqueued.
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


async def test_stranded_queued_row_is_re_enqueued(real_redis, active_user):
    jobs = get_job_service()
    job_id = uuid.uuid4()
    # Persisted QUEUED but the LPUSH never happened (API crash): not on redis.
    await jobs.create_job(job_id=job_id, flow_id=uuid.uuid4(), user_id=active_user.id)

    backend = _scoped_backend(real_redis, jobs)
    pending = await real_redis.lrange(backend.claim_queue.pending_key, 0, -1)
    assert str(job_id).encode() not in pending  # confirm stranded

    recovered = await backend.recover_stranded_queued()
    assert str(job_id) in recovered

    # Now on pending and back to QUEUED so a real worker re-runs it.
    pending = await real_redis.lrange(backend.claim_queue.pending_key, 0, -1)
    assert str(job_id).encode() in pending
    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.QUEUED


async def test_enqueued_queued_row_not_double_enqueued(real_redis, active_user):
    """A QUEUED row already on the pending list is left alone (no duplicate)."""
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid.uuid4(), user_id=active_user.id)

    backend = _scoped_backend(real_redis, jobs)
    await backend.enqueue(str(job_id))  # properly enqueued

    recovered = await backend.recover_stranded_queued()
    assert str(job_id) not in recovered
    pending = await real_redis.lrange(backend.claim_queue.pending_key, 0, -1)
    assert pending.count(str(job_id).encode()) == 1  # exactly one entry, not two


async def test_recover_is_single_flight_across_two_backends(real_redis, active_user):
    """Two workers' recovery passes re-enqueue a stranded row only once."""
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid.uuid4(), user_id=active_user.id)

    backend_a = _scoped_backend(real_redis, jobs)
    backend_b = _scoped_backend(real_redis, jobs)

    rec_a = await backend_a.recover_stranded_queued()
    rec_b = await backend_b.recover_stranded_queued()
    # Exactly one of the two recovered it (claim_queued_job is the single-flight).
    assert (str(job_id) in rec_a) ^ (str(job_id) in rec_b)
    pending = await real_redis.lrange(backend_a.claim_queue.pending_key, 0, -1)
    assert pending.count(str(job_id).encode()) == 1
