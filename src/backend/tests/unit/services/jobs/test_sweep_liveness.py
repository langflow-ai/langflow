"""sweep_orphans must be liveness-aware: never fail a job with a FRESH heartbeat.

The startup sweep ran on every worker boot and marked EVERY IN_PROGRESS row
FAILED(worker_lost). Under gunicorn -w N a booting worker B would flip worker
A's just-claimed, actively-running job FAILED mid-run. The fix: only reconcile
IN_PROGRESS rows whose heartbeat is stale/absent; a fresh heartbeat means a live
owner is running it and the sweep must leave it alone.
"""

from __future__ import annotations

import asyncio
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


@pytest.mark.usefixtures("client")
async def test_keep_alive_spares_a_running_job_from_the_sweep():
    """A job kept alive by its running process outlives the lease and is not swept."""
    service = JobService()
    job_id = uuid4()
    dead = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4(), status=JobStatus.IN_PROGRESS)
    await service.create_job(job_id=dead, flow_id=uuid4(), user_id=uuid4(), status=JobStatus.IN_PROGRESS)

    await service.start_keep_alive(job_id, interval_s=0.1)
    try:
        # Longer than the lease: only the periodic heartbeat keeps the job fresh.
        await asyncio.sleep(1.5)
        swept = await service.sweep_orphans(lease_ttl_s=1.0)
    finally:
        await service.stop_keep_alive(job_id)

    assert swept == [dead]  # The same sweep still fails a job nobody keeps alive.
    job = await service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.IN_PROGRESS
    assert await service.read_events(job_id) == []


@pytest.mark.usefixtures("client")
async def test_keep_alive_stops_once_the_job_ends():
    """No heartbeat lands after the job leaves IN_PROGRESS, even if nobody stops it."""
    service = JobService()
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4(), status=JobStatus.IN_PROGRESS)
    await service.start_keep_alive(job_id, interval_s=0.1)

    await service.update_job_status(job_id, JobStatus.CANCELLED, finished_timestamp=True)
    await asyncio.sleep(0.5)
    stamp = (await service.get_job_by_job_id(job_id)).job_metadata["heartbeat_at"]
    await asyncio.sleep(0.3)

    assert (await service.get_job_by_job_id(job_id)).job_metadata["heartbeat_at"] == stamp
    assert job_id not in service._keep_alives
    await service.stop_keep_alive(job_id)  # Already ended on its own; still safe.


@pytest.mark.usefixtures("client")
async def test_stop_keep_alive_waits_for_an_in_flight_heartbeat(monkeypatch):
    """Once stop returns, no heartbeat write is in flight, so the owner can write job_metadata."""
    service = JobService()
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4(), status=JobStatus.IN_PROGRESS)
    beat = service._beat
    in_flight = asyncio.Event()
    release = asyncio.Event()

    async def slow_beat(job):
        in_flight.set()
        await release.wait()
        return await beat(job)

    monkeypatch.setattr(service, "_beat", slow_beat)
    await service.start_keep_alive(job_id, interval_s=0.1)
    await asyncio.wait_for(in_flight.wait(), timeout=5)

    stopping = asyncio.create_task(service.stop_keep_alive(job_id))
    await asyncio.sleep(0.2)
    assert not stopping.done()
    release.set()
    await asyncio.wait_for(stopping, timeout=5)

    await service.update_job_metadata(job_id, {"status": "succeeded"})
    stamp = (await service.get_job_by_job_id(job_id)).job_metadata["heartbeat_at"]
    await asyncio.sleep(0.3)
    metadata = (await service.get_job_by_job_id(job_id)).job_metadata
    assert metadata["status"] == "succeeded"
    assert metadata["heartbeat_at"] == stamp
