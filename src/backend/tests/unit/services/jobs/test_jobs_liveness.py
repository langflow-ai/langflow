"""Store-layer liveness primitives: heartbeat, stale predicate, atomic attempt.

These back the lease+heartbeat reconciliation model. A reconciler must only
fail/requeue a job whose heartbeat is STALE (older than the lease TTL), never a
fresh one, and the retry-safe attempt bump must be atomic so two concurrent
reconcilers cannot push a job past max_attempts.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.jobs.service import JobService


@pytest.mark.usefixtures("client")
async def test_heartbeat_records_owner_and_timestamp():
    service = JobService()
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    before = datetime.now(timezone.utc)
    await service.heartbeat(job_id, owner="worker-A")
    after = datetime.now(timezone.utc)

    job = await service.get_job_by_job_id(job_id)
    meta = job.job_metadata or {}
    assert meta.get("owner") == "worker-A"
    hb = datetime.fromisoformat(meta["heartbeat_at"])
    assert before <= hb <= after


@pytest.mark.usefixtures("client")
async def test_heartbeat_preserves_other_metadata():
    service = JobService()
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_metadata(job_id, {"request": {"input_value": "hi"}, "retry_safe": True})

    await service.heartbeat(job_id, owner="worker-A")

    job = await service.get_job_by_job_id(job_id)
    meta = job.job_metadata or {}
    # Heartbeat must not clobber the persisted request / retry flag.
    assert meta["request"] == {"input_value": "hi"}
    assert meta["retry_safe"] is True
    assert meta["owner"] == "worker-A"


@pytest.mark.usefixtures("client")
async def test_is_lease_stale_fresh_vs_stale():
    service = JobService()
    fresh = uuid4()
    stale = uuid4()
    absent = uuid4()
    await service.create_job(job_id=fresh, flow_id=uuid4(), user_id=uuid4())
    await service.create_job(job_id=stale, flow_id=uuid4(), user_id=uuid4())
    await service.create_job(job_id=absent, flow_id=uuid4(), user_id=uuid4())

    await service.heartbeat(fresh, owner="w1")
    # Backdate the stale job's heartbeat well past the TTL.
    old = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    await service.update_job_metadata(stale, {"owner": "w1", "heartbeat_at": old})

    fresh_job = await service.get_job_by_job_id(fresh)
    stale_job = await service.get_job_by_job_id(stale)
    absent_job = await service.get_job_by_job_id(absent)

    assert service.is_lease_stale(fresh_job, lease_ttl_s=30.0) is False
    assert service.is_lease_stale(stale_job, lease_ttl_s=30.0) is True
    # No heartbeat ever recorded -> treated as stale (truly orphaned / never ran).
    assert service.is_lease_stale(absent_job, lease_ttl_s=30.0) is True


@pytest.mark.usefixtures("client")
async def test_increment_attempt_atomic_is_conditional():
    """Atomic attempt bump only succeeds when it observes the expected value.

    This is the optimistic guard that prevents two concurrent reconcilers from
    both reading attempt=1 and both writing attempt=2 (a lost update).
    """
    service = JobService()
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_metadata(job_id, {"attempt": 1, "max_attempts": 3})

    # First bump from 1 -> 2 wins.
    assert await service.increment_attempt_if(job_id, expected=1, new=2) is True
    job = await service.get_job_by_job_id(job_id)
    assert job.job_metadata["attempt"] == 2

    # A racer that still thinks attempt==1 must NOT bump it again.
    assert await service.increment_attempt_if(job_id, expected=1, new=2) is False
    job = await service.get_job_by_job_id(job_id)
    assert job.job_metadata["attempt"] == 2


@pytest.mark.usefixtures("client")
async def test_increment_attempt_concurrent_only_one_wins():
    """Under concurrent bumps from the same expected value exactly one wins."""
    service = JobService()
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_metadata(job_id, {"attempt": 1, "max_attempts": 5})

    results = await asyncio.gather(*(service.increment_attempt_if(job_id, expected=1, new=2) for _ in range(8)))
    assert results.count(True) == 1
    job = await service.get_job_by_job_id(job_id)
    assert job.job_metadata["attempt"] == 2
