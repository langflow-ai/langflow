"""DB-derived metric collector queries over the real durable job model.

These are pure read-only aggregates the collector loop pushes to OTel gauges.
They run against the REAL test DB (the ``client`` fixture; SQLite locally,
Postgres in CI) with NO mocking. ``now`` is injected so the time math is
deterministic and never races the wall clock.

The "alive" definition MUST match the watchdog's lease-staleness boundary
(``JobService.is_lease_stale``): a heartbeat is FRESH while its age is within
the lease window, so ``alive_worker_count`` counts owners with
``heartbeat_at >= now - lease_window``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.background_execution.metrics_collector import (
    alive_worker_count,
    count_nonterminal_jobs,
    oldest_queued_seconds,
)
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import session_scope
from langflow.services.jobs.service import JobService

pytestmark = pytest.mark.usefixtures("client")


async def test_count_nonterminal_jobs_excludes_terminal():
    """Only non-terminal statuses are counted, keyed by status string."""
    service = JobService()

    queued_a = uuid4()
    queued_b = uuid4()
    in_progress = uuid4()
    completed = uuid4()

    await service.create_job(job_id=queued_a, flow_id=uuid4(), user_id=uuid4())
    await service.create_job(job_id=queued_b, flow_id=uuid4(), user_id=uuid4())

    await service.create_job(job_id=in_progress, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(in_progress, JobStatus.IN_PROGRESS)

    # Terminal: must be excluded from the non-terminal aggregate.
    await service.create_job(job_id=completed, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(completed, JobStatus.COMPLETED, finished_timestamp=True)

    async with session_scope() as session:
        counts = await count_nonterminal_jobs(session)

    assert counts == {"queued": 2, "in_progress": 1}


async def test_oldest_queued_seconds_uses_injected_now():
    """Age of the oldest QUEUED job == now - min(created_timestamp)."""
    service = JobService()

    older = uuid4()
    newer = uuid4()
    await service.create_job(job_id=older, flow_id=uuid4(), user_id=uuid4())
    await service.create_job(job_id=newer, flow_id=uuid4(), user_id=uuid4())

    # Read back the actual stored created_timestamp of the oldest QUEUED job so
    # the expected age is exact regardless of insert latency.
    older_job = await service.get_job_by_job_id(older)
    created = older_job.created_timestamp
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    now = created + timedelta(seconds=42)

    async with session_scope() as session:
        age = await oldest_queued_seconds(session, now)

    assert age == pytest.approx(42.0, abs=1.0)


async def test_oldest_queued_seconds_zero_when_none_queued():
    """No QUEUED jobs -> 0.0 (a COMPLETED job must not count)."""
    service = JobService()

    done = uuid4()
    await service.create_job(job_id=done, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(done, JobStatus.COMPLETED, finished_timestamp=True)

    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        age = await oldest_queued_seconds(session, now)

    assert age == 0.0


async def test_alive_worker_count_excludes_stale_heartbeats():
    """Distinct owners with a FRESH heartbeat (within the lease window) are alive.

    Two owners heartbeat fresh; one owner's heartbeat is older than the window.
    The stale owner is excluded, matching ``is_lease_stale``.
    """
    service = JobService()
    lease_window = 30.0

    fresh_a = uuid4()
    fresh_b = uuid4()
    stale = uuid4()

    await service.create_job(job_id=fresh_a, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(fresh_a, JobStatus.IN_PROGRESS)
    await service.heartbeat(fresh_a, owner="worker-A")

    await service.create_job(job_id=fresh_b, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(fresh_b, JobStatus.IN_PROGRESS)
    await service.heartbeat(fresh_b, owner="worker-B")

    await service.create_job(job_id=stale, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(stale, JobStatus.IN_PROGRESS)
    old = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    await service.update_job_metadata(stale, {"owner": "worker-dead", "heartbeat_at": old})

    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        alive = await alive_worker_count(session, now, lease_window)

    assert alive == 2


async def test_alive_worker_count_distinct_owner():
    """Multiple fresh heartbeats from the SAME owner count once."""
    service = JobService()
    lease_window = 30.0

    job_one = uuid4()
    job_two = uuid4()
    await service.create_job(job_id=job_one, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(job_one, JobStatus.IN_PROGRESS)
    await service.heartbeat(job_one, owner="worker-A")

    await service.create_job(job_id=job_two, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(job_two, JobStatus.IN_PROGRESS)
    await service.heartbeat(job_two, owner="worker-A")

    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        alive = await alive_worker_count(session, now, lease_window)

    assert alive == 1
