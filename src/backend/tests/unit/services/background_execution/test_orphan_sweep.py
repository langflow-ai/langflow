"""Startup orphan sweep: re-enqueue QUEUED, fail orphaned IN_PROGRESS."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from filelock import FileLock
from langflow.services.background_execution import service as service_module
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_job_service, get_settings_service

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.usefixtures("client")


@pytest.fixture(autouse=True)
def _per_test_sweep_lock(monkeypatch, tmp_path):
    """Give each test its own startup-sweep lock.

    The real lock lives in the system temp dir. Under xdist, another worker's app
    startup can hold it, and this test's sweep then skips the reconcile it asserts.
    """
    monkeypatch.setattr(
        service_module, "FileLock", lambda path, **kwargs: FileLock(tmp_path / Path(path).name, **kwargs)
    )


def _frame(event_type, data):
    return (json.dumps({"event": event_type, "data": data}).encode("utf-8"), event_type)


async def _scripted(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
    yield _frame("end", {})


async def test_orphaned_in_progress_marked_failed(active_user):
    job_service = get_job_service()
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=active_user.id)
    # Simulate a crash mid-flight: status stuck at IN_PROGRESS, no live task.
    await job_service.update_job_status(job_id, JobStatus.IN_PROGRESS)

    svc = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=lambda **_kw: _scripted,
    )
    await svc.start()
    try:
        await svc.sweep_orphans_on_startup()
        job = await job_service.get_job_by_job_id(job_id)
        assert job.status == JobStatus.FAILED
        assert job.error is not None
        assert job.error.get("type") == "worker_lost"
    finally:
        await svc.stop()


async def test_startup_sweep_spares_fresh_heartbeat_job(active_user):
    """A live IN_PROGRESS job (fresh heartbeat) survives a booting worker's sweep."""
    job_service = get_job_service()
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=active_user.id)
    await job_service.update_job_status(job_id, JobStatus.IN_PROGRESS)
    # Another (live) worker is running this job and just heartbeated it.
    await job_service.heartbeat(job_id, owner="sibling-worker")

    svc = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=lambda **_kw: _scripted,
    )
    await svc.start()
    try:
        await svc.sweep_orphans_on_startup()
        job = await job_service.get_job_by_job_id(job_id)
        # Not flipped FAILED: the sibling's live run is left alone.
        assert job.status == JobStatus.IN_PROGRESS
        assert job.error is None
        assert all(e.event_type != "run_failed" for e in await job_service.read_events(job_id))
    finally:
        await svc.stop()


async def test_orphaned_queued_is_re_enqueued_and_runs(active_user):
    job_service = get_job_service()
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=active_user.id)
    # Left QUEUED by a crash before the worker picked it up.

    svc = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=lambda **_kw: _scripted,
    )
    await svc.start()
    try:
        await svc.sweep_orphans_on_startup()
        job = None
        for _ in range(50):
            job = await job_service.get_job_by_job_id(job_id)
            if job.status == JobStatus.COMPLETED:
                break
            await asyncio.sleep(0.05)
        assert job.status == JobStatus.COMPLETED
    finally:
        await svc.stop()


async def test_queued_claimed_then_crashed_is_rerun_not_failed(active_user):
    """A QUEUED job lease-claimed by a sweep that crashed before running stays re-runnable.

    Regression: the old re-enqueue flipped QUEUED->IN_PROGRESS at claim time, so a
    crash before the runner started left a stranded IN_PROGRESS the next sweep
    marked FAILED(worker_lost) — a job that never executed any side effect ended
    FAILED. With lease-claim the row stays QUEUED and the next boot re-runs it.
    """
    job_service = get_job_service()
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=active_user.id)
    await job_service.update_job_metadata(job_id, {"request": {"stream_protocol": "langflow"}})

    # Simulate worker 1: lease-claimed the QUEUED row, then crashed BEFORE the
    # runner started (so the row is still QUEUED, with a STALE lease the next
    # boot's default 45s-TTL sweep will treat as orphaned and re-claim).
    from datetime import datetime, timedelta, timezone

    old = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    await job_service.update_job_metadata(job_id, {"owner": "dead-worker", "heartbeat_at": old})
    crashed = await job_service.get_job_by_job_id(job_id)
    assert crashed.status == JobStatus.QUEUED  # never flipped IN_PROGRESS

    # Worker 2 boots: the lease is stale, so the sweep re-claims and re-runs it.
    svc = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=lambda **_kw: _scripted,
    )
    await svc.start()
    try:
        await svc.sweep_orphans_on_startup()
        job = None
        for _ in range(50):
            job = await job_service.get_job_by_job_id(job_id)
            if job.status == JobStatus.COMPLETED:
                break
            await asyncio.sleep(0.05)
        assert job.status == JobStatus.COMPLETED  # re-ran, NOT FAILED(worker_lost)
        assert (job.error or {}).get("type") != "worker_lost"
    finally:
        await svc.stop()


async def test_startup_enqueue_failure_releases_queued_lease(active_user, monkeypatch):
    """A failed enqueue must not leave a QUEUED row owned by work that was never scheduled."""
    job_service = get_job_service()
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=active_user.id)

    svc = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=lambda **_kw: _scripted,
    )

    async def fail_enqueue(**_kwargs):
        msg = "executor unavailable"
        raise RuntimeError(msg)

    monkeypatch.setattr(svc, "_enqueue", fail_enqueue)

    await svc.start()
    try:
        await svc.sweep_orphans_on_startup()
        job = await job_service.get_job_by_job_id(job_id)
        assert job.status == JobStatus.QUEUED
        assert "owner" not in (job.job_metadata or {})
        assert "heartbeat_at" not in (job.job_metadata or {})
        # The released row is immediately claimable again instead of waiting for the lease TTL.
        assert await job_service.claim_queued_lease(
            job_id,
            owner="next-boot",
            lease_ttl_s=get_settings_service().settings.background_lease_ttl_s,
        )
    finally:
        await svc.stop()


async def test_startup_reconciles_an_orphan_once_its_lease_expires(active_user, monkeypatch):
    """A run whose worker died just before this boot is failed once its heartbeat goes stale.

    The dead worker's last heartbeat is still fresh when the startup sweep runs,
    so that sweep must spare it. Without a later pass, the default (non-Redis)
    mode never sweeps again and the run stays IN_PROGRESS until the next restart.
    The later pass must leave alone runs that never heartbeat, such as a
    synchronous run this process started after boot.
    """
    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.settings, "background_lease_ttl_s", 1.0)
    job_service = get_job_service()
    orphan_id = uuid4()
    await job_service.create_job(
        job_id=orphan_id, flow_id=uuid4(), user_id=active_user.id, status=JobStatus.IN_PROGRESS
    )
    # The previous process heartbeated moments before it died.
    await job_service.heartbeat(orphan_id, owner="dead-worker")

    svc = BackgroundExecutionService(
        settings_service=settings_service,
        frame_source_factory=lambda **_kw: _scripted,
    )
    await svc.start()
    try:
        await svc.sweep_orphans_on_startup()
        assert (await job_service.get_job_by_job_id(orphan_id)).status == JobStatus.IN_PROGRESS
        # A synchronous run started after boot: in progress, never heartbeats.
        live_id = uuid4()
        await job_service.create_job(
            job_id=live_id, flow_id=uuid4(), user_id=active_user.id, status=JobStatus.IN_PROGRESS
        )

        orphan = None
        for _ in range(80):
            orphan = await job_service.get_job_by_job_id(orphan_id)
            if orphan.status == JobStatus.FAILED:
                break
            await asyncio.sleep(0.05)
        assert orphan.status == JobStatus.FAILED
        assert (orphan.error or {}).get("type") == "worker_lost"
        live = await job_service.get_job_by_job_id(live_id)
        assert live.status == JobStatus.IN_PROGRESS
        assert live.error is None
    finally:
        await svc.stop()


async def test_stop_cancels_the_pending_lease_expiry_sweep():
    svc = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=lambda **_kw: _scripted,
    )
    await svc.start()
    await svc.sweep_orphans_on_startup()
    pending = svc._lease_expiry_task
    assert pending is not None
    assert not pending.done()

    await svc.stop()

    assert pending.cancelled()
