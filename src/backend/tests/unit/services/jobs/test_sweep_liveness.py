"""sweep_orphans must be liveness-aware: never fail a job with a FRESH heartbeat.

The startup sweep ran on every worker boot and marked EVERY IN_PROGRESS row
FAILED(worker_lost). Under gunicorn -w N a booting worker B would flip worker
A's just-claimed, actively-running job FAILED mid-run. The fix: only reconcile
IN_PROGRESS rows whose heartbeat is stale/absent; a fresh heartbeat means a live
owner is running it and the sweep must leave it alone.

Only the background runner heartbeats. Sync and stream runs never do, so a row
with no heartbeat is only reconciled once it is older than the longest a live
client-attached run can last (``JobService.no_heartbeat_grace_s``).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.jobs.service import JobService
from sqlmodel import update


async def _backdate(job_id, seconds: float) -> None:
    """Age a row: a run that never heartbeats has only its created_timestamp as a clock."""
    created = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    async with session_scope() as session:
        await session.exec(update(Job).where(Job.job_id == job_id).values(created_timestamp=created))


@pytest.mark.usefixtures("client")
async def test_sweep_skips_fresh_heartbeat_job():
    """A live in-progress job (fresh heartbeat) is NOT failed by the sweep."""
    service = JobService()
    live = uuid4()
    dead = uuid4()
    await service.create_job(job_id=live, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(live, JobStatus.IN_PROGRESS)
    await service.heartbeat(live, owner="worker-A")  # fresh: live owner running it

    await service.create_job(job_id=dead, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(dead, JobStatus.IN_PROGRESS)
    old = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    await service.update_job_metadata(dead, {"owner": "worker-B", "heartbeat_at": old})

    swept = await service.sweep_orphans(lease_ttl_s=30.0)

    # Only the stale (dead) job is reconciled.
    assert dead in swept
    assert live not in swept

    live_job = await service.get_job_by_job_id(live)
    assert live_job.status == JobStatus.IN_PROGRESS  # untouched, no phantom failure
    assert await service.read_events(live) == []  # no phantom terminal event injected

    dead_job = await service.get_job_by_job_id(dead)
    assert dead_job.status == JobStatus.FAILED
    assert (dead_job.error or {}).get("type") == "worker_lost"


@pytest.mark.usefixtures("client")
async def test_sweep_spares_young_heartbeatless_in_progress():
    """Sync and stream runs never heartbeat; while young one may be live on any replica."""
    service = JobService()
    run = uuid4()
    await service.create_job(job_id=run, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(run, JobStatus.IN_PROGRESS)

    swept = await service.sweep_orphans(lease_ttl_s=45.0)

    assert run not in swept
    job = await service.get_job_by_job_id(run)
    assert job.status == JobStatus.IN_PROGRESS
    assert job.error is None
    assert await service.read_events(run) == []


@pytest.mark.usefixtures("client")
async def test_sweep_fails_heartbeatless_in_progress_past_the_grace():
    """Past workflow_execution_timeout plus the lease TTL, no live run can own the row."""
    service = JobService()
    grace = JobService.no_heartbeat_grace_s(45.0)
    assert grace == get_settings_service().settings.workflow_execution_timeout + 45.0
    orphan = uuid4()
    recent = uuid4()
    for job_id in (orphan, recent):
        await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
        await service.update_job_status(job_id, JobStatus.IN_PROGRESS)
    await _backdate(orphan, grace + 5)
    await _backdate(recent, grace - 5)

    swept = await service.sweep_orphans(lease_ttl_s=45.0)

    assert orphan in swept
    assert recent not in swept
    job = await service.get_job_by_job_id(orphan)
    assert job.status == JobStatus.FAILED
    assert job.error == {"type": "worker_lost"}
    events = await service.read_events(orphan)
    assert [event.event_type for event in events] == ["run_failed"]
    assert (await service.get_job_by_job_id(recent)).status == JobStatus.IN_PROGRESS


@pytest.mark.usefixtures("client")
async def test_heartbeating_rows_keep_the_lease_rule_regardless_of_age():
    """Background runs heartbeat, so their lease alone decides, however young or old the row."""
    service = JobService()
    young_dead = uuid4()
    old_live = uuid4()
    for job_id in (young_dead, old_live):
        await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
        await service.update_job_status(job_id, JobStatus.IN_PROGRESS)
    stale = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    await service.update_job_metadata(young_dead, {"owner": "dead-worker", "heartbeat_at": stale})
    await _backdate(old_live, JobService.no_heartbeat_grace_s(45.0) + 60)
    await service.heartbeat(old_live, owner="live-worker")

    swept = await service.sweep_orphans(lease_ttl_s=45.0)

    assert young_dead in swept
    assert old_live not in swept
    assert (await service.get_job_by_job_id(old_live)).status == JobStatus.IN_PROGRESS


@pytest.mark.usefixtures("client")
async def test_run_reaped_mid_flight_finishes_completed_without_the_sweep_error():
    """A run that outlived its grace and was reaped must not end COMPLETED with worker_lost."""
    service = JobService()
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    async def run() -> str:
        assert job_id in await service.sweep_orphans(lease_ttl_s=45.0, no_heartbeat_grace_s=0.0)
        return "done"

    assert await service.execute_with_status(job_id, run) == "done"

    job = await service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED
    assert job.error is None
    assert job.finished_timestamp is not None

    # Only COMPLETED clears it: a failed run keeps its error.
    await service.update_job_status(job_id, JobStatus.FAILED, finished_timestamp=True)
    await service.set_error(job_id, {"type": "boom"})
    await service.update_job_status(job_id, JobStatus.FAILED, finished_timestamp=True)
    assert (await service.get_job_by_job_id(job_id)).error == {"type": "boom"}


@pytest.mark.usefixtures("client")
async def test_concurrent_sweeps_reconcile_an_orphan_once():
    """Two replicas racing the same stale row emit one terminal transition."""
    service = JobService()
    orphan = uuid4()
    await service.create_job(job_id=orphan, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(orphan, JobStatus.IN_PROGRESS)
    old = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    await service.update_job_metadata(orphan, {"owner": "dead-worker", "heartbeat_at": old})

    results = await asyncio.gather(
        service.sweep_orphans(lease_ttl_s=30.0),
        service.sweep_orphans(lease_ttl_s=30.0),
    )

    assert sum(result.count(orphan) for result in results) == 1
    events = await service.read_events(orphan)
    assert [event.event_type for event in events] == ["run_failed"]
