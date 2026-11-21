"""Lease watchdog on the DB backend: stale IN_PROGRESS fails worker_lost; retry-safe requeues to max.

QUEUED rows need no watchdog pass at all — the durable row is the queue, so a
stale-leased QUEUED job is simply claimable again (covered in test_db_backend).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langflow.services.background_execution import db_backend
from langflow.services.background_execution.db_backend import DBBackgroundQueue
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
async def test_in_progress_lost_job_fails_worker_lost(active_user):
    flow_id = uuid.uuid4()
    jobs, job_id = await _make_job(flow_id, status=JobStatus.IN_PROGRESS, user_id=active_user.id)

    backend = DBBackgroundQueue(job_service=jobs)
    await backend.requeue_lost()

    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.FAILED
    # set_error stores {"type": "worker_lost"} on the durable job.error column.
    err = refreshed.error or {}
    assert err.get("type") == "worker_lost"
    # A terminal run_failed event ends any reattached tail cleanly.
    events = await jobs.read_events(job_id)
    assert any(e.event_type == "run_failed" for e in events)


@pytest.mark.usefixtures("client")
@pytest.mark.asyncio
async def test_in_progress_with_fresh_lease_is_left_alone(active_user):
    flow_id = uuid.uuid4()
    jobs, job_id = await _make_job(flow_id, status=JobStatus.IN_PROGRESS, user_id=active_user.id)
    # A live worker just heartbeated: the watchdog must not reap this run.
    await jobs.heartbeat(job_id, "worker:live")

    backend = DBBackgroundQueue(job_service=jobs)
    await backend.requeue_lost(lease_ttl_s=45.0)

    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.IN_PROGRESS


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

    backend = DBBackgroundQueue(job_service=jobs)
    requeued = await backend.requeue_lost()

    assert str(job_id) in requeued
    refreshed = await jobs.get_job_by_job_id(job_id)
    # Flipped back to QUEUED (claimable by any worker) with the attempt bumped.
    assert refreshed.status == JobStatus.QUEUED
    assert refreshed.job_metadata["attempt"] == 2


@pytest.mark.usefixtures("client")
@pytest.mark.asyncio
async def test_concurrent_watchdogs_cap_retry_attempts(active_user):
    """N concurrent requeue_lost calls bump attempt exactly once (atomic accounting).

    Restores the concurrency proof the deleted redis suite carried: the
    conditional retry_requeue_claim UPDATE (guarded on attempt==expected AND
    status==IN_PROGRESS) means racing watchdogs cannot push a job past
    max_attempts. SQLite serializes writers, so this is strongest on Postgres,
    but the single-flight assertion holds on both.
    """
    import asyncio

    flow_id = uuid.uuid4()
    jobs, job_id = await _make_job(
        flow_id,
        status=JobStatus.IN_PROGRESS,
        user_id=active_user.id,
        metadata={"retry_safe": True, "max_attempts": 2, "attempt": 1},
    )

    backends = [DBBackgroundQueue(job_service=jobs, owner=f"worker:{i}") for i in range(6)]
    results = await asyncio.gather(*(b.requeue_lost() for b in backends))

    requeue_counts = sum(str(job_id) in r for r in results)
    assert requeue_counts == 1, f"expected exactly one watchdog to requeue, got {requeue_counts}"
    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.QUEUED
    # Bumped exactly once — never past max_attempts.
    assert refreshed.job_metadata["attempt"] == 2


@pytest.mark.usefixtures("client")
@pytest.mark.asyncio
async def test_concurrent_watchdogs_append_one_terminal_event(active_user):
    """N concurrent requeue_lost calls on a default orphan write ONE run_failed.

    The conditional IN_PROGRESS->FAILED flip is the single-flight token: only
    the watchdog whose UPDATE matched appends the terminal milestone, so the
    durable event log carries exactly one clean end.
    """
    import asyncio

    flow_id = uuid.uuid4()
    jobs, job_id = await _make_job(flow_id, status=JobStatus.IN_PROGRESS, user_id=active_user.id)

    backends = [DBBackgroundQueue(job_service=jobs, owner=f"worker:{i}") for i in range(6)]
    await asyncio.gather(*(b.requeue_lost() for b in backends))

    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.FAILED
    events = await jobs.read_events(job_id)
    terminal = [e for e in events if e.event_type == "run_failed"]
    assert len(terminal) == 1, f"expected exactly one run_failed event, got {len(terminal)}"


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

    backend = DBBackgroundQueue(job_service=jobs)
    requeued = await backend.requeue_lost()

    assert str(job_id) not in requeued
    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.FAILED
    err = refreshed.error or {}
    assert err.get("type") == "worker_lost"


@pytest.mark.usefixtures("client")
@pytest.mark.parametrize("malformed_field", ["attempt", "max_attempts"])
async def test_malformed_retry_metadata_does_not_abandon_later_orphans(active_user, monkeypatch, malformed_field):
    metadata = {"retry_safe": True, "max_attempts": 3, "attempt": 1, malformed_field: "not-a-number"}
    jobs, malformed_id = await _make_job(
        uuid.uuid4(), status=JobStatus.IN_PROGRESS, user_id=active_user.id, metadata=metadata
    )
    _, healthy_id = await _make_job(uuid.uuid4(), status=JobStatus.IN_PROGRESS, user_id=active_user.id)
    list_in_progress = jobs.in_progress_workflow_job_ids

    async def malformed_first():
        # The query has no ordering guarantee, so put the malformed row first.
        job_ids = await list_in_progress()
        return sorted(job_ids, key=lambda job_id: job_id != malformed_id)

    monkeypatch.setattr(jobs, "in_progress_workflow_job_ids", malformed_first)
    log_exception = AsyncMock()
    monkeypatch.setattr(db_backend, "logger", SimpleNamespace(aexception=log_exception))
    backend = DBBackgroundQueue(job_service=jobs)

    assert await backend.requeue_lost() == []

    log_exception.assert_awaited_once()
    assert str(malformed_id) in log_exception.await_args.args[0]
    malformed = await jobs.get_job_by_job_id(malformed_id)
    assert malformed.status == JobStatus.IN_PROGRESS
    assert malformed.job_metadata[malformed_field] == "not-a-number"
    assert malformed.error is None
    assert await jobs.read_events(malformed_id) == []
    healthy = await jobs.get_job_by_job_id(healthy_id)
    assert healthy.status == JobStatus.FAILED
    assert healthy.error == {"type": "worker_lost"}
    events = await jobs.read_events(healthy_id)
    assert [event.event_type for event in events] == ["run_failed"]

    assert await backend.requeue_lost() == []

    assert log_exception.await_count == 2
    assert str(malformed_id) in log_exception.await_args.args[0]
    events = await jobs.read_events(healthy_id)
    assert [event.event_type for event in events] == ["run_failed"]
