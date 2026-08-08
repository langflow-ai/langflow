"""sweep_orphans must be liveness-aware: never fail a job with a FRESH heartbeat.

The startup sweep ran on every worker boot and marked EVERY IN_PROGRESS row
FAILED(worker_lost). Under gunicorn -w N a booting worker B would flip worker
A's just-claimed, actively-running job FAILED mid-run. The fix: only reconcile
IN_PROGRESS rows whose heartbeat is stale/absent; a fresh heartbeat means a live
owner is running it and the sweep must leave it alone.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.jobs.service import JobService


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
async def test_sweep_still_fails_heartbeatless_in_progress():
    """An IN_PROGRESS row that never recorded a heartbeat is a real orphan."""
    service = JobService()
    orphan = uuid4()
    await service.create_job(job_id=orphan, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(orphan, JobStatus.IN_PROGRESS)

    swept = await service.sweep_orphans(lease_ttl_s=30.0)
    assert orphan in swept
    job = await service.get_job_by_job_id(orphan)
    assert job.status == JobStatus.FAILED
    events = await service.read_events(orphan)
    assert len(events) == 1
    assert events[0].event_type == "run_failed"
