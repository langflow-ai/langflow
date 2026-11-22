"""Scaled startup maintenance and terminal-event reattachment use the durable store."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.background_execution import service as service_module
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.deps import get_job_service, get_settings_service, session_scope

pytestmark = pytest.mark.usefixtures("client")


def _scaled_service(monkeypatch) -> BackgroundExecutionService:
    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.settings, "background_backend", "scaled")
    monkeypatch.setattr(settings_service.settings, "background_watchdog_interval_s", 0.01)
    monkeypatch.setattr(settings_service.settings, "background_poll_interval_s", 0.01)
    return BackgroundExecutionService(settings_service)


async def test_scaled_startup_expires_existing_input_deadlines_without_a_submission(active_user, monkeypatch):
    jobs = get_job_service()
    job_id = uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid4(), user_id=active_user.id, status=JobStatus.SUSPENDED)
    await jobs.update_job_metadata(
        job_id, {"input_deadline_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}
    )
    monkeypatch.setattr(get_settings_service().settings, "background_input_deadline_s", 1.0)
    expired = asyncio.Event()
    sweep = jobs.sweep_input_deadlines

    async def observe_expiration():
        failed = await sweep()
        if job_id in failed:
            expired.set()
        return failed

    monkeypatch.setattr(jobs, "sweep_input_deadlines", observe_expiration)
    service = _scaled_service(monkeypatch)
    try:
        await service.sweep_orphans_on_startup()
        await asyncio.wait_for(expired.wait(), timeout=2)
        assert (await jobs.get_job_by_job_id(job_id)).status == JobStatus.FAILED
    finally:
        await service.stop()


async def test_scaled_startup_purges_old_jobs_without_a_submission(active_user, monkeypatch):
    jobs = get_job_service()
    job_id = uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid4(), user_id=active_user.id, status=JobStatus.COMPLETED)
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        job.finished_timestamp = datetime.now(timezone.utc) - timedelta(days=2)
        session.add(job)

    monkeypatch.setattr(get_settings_service().settings, "background_retention_days", 1)
    monkeypatch.setattr(service_module, "_RETENTION_INITIAL_DELAY_S", 0.01)
    purged = asyncio.Event()
    purge = jobs.purge_terminal_jobs

    async def observe_purge(**kwargs):
        deleted = await purge(**kwargs)
        if await jobs.get_job_by_job_id(job_id) is None:
            purged.set()
        return deleted

    monkeypatch.setattr(jobs, "purge_terminal_jobs", observe_purge)
    service = _scaled_service(monkeypatch)
    try:
        await service.sweep_orphans_on_startup()
        await asyncio.wait_for(purged.wait(), timeout=2)
        assert await jobs.get_job_by_job_id(job_id) is None
    finally:
        await service.stop()


@pytest.mark.parametrize(
    ("status", "event_type"),
    [
        (JobStatus.CANCELLED, "run_cancelled"),
        (JobStatus.TIMED_OUT, "run_timed_out"),
        (JobStatus.FAILED, "run_failed"),
    ],
)
async def test_scaled_terminal_reattach_waits_for_the_terminal_event(active_user, monkeypatch, status, event_type):
    jobs = get_job_service()
    job_id = uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid4(), user_id=active_user.id)
    cursor = await jobs.append_event(job_id, "build_start", {})
    await jobs.update_job_status(job_id, status, finished_timestamp=True)
    first_replay = asyncio.Event()
    read_events = jobs.read_events

    async def observe_first_replay(read_job_id, *, after_seq=0):
        rows = await read_events(read_job_id, after_seq=after_seq)
        if read_job_id == job_id:
            first_replay.set()
        return rows

    monkeypatch.setattr(jobs, "read_events", observe_first_replay)
    service = _scaled_service(monkeypatch)

    async def append_after_replay():
        await first_replay.wait()
        await jobs.append_event(job_id, event_type, {"type": event_type})

    async def reattach():
        return [frame async for frame in service.events(job_id, last_event_id=str(cursor), user=active_user)]

    try:
        frames, _ = await asyncio.wait_for(asyncio.gather(reattach(), append_after_replay()), timeout=2)
        assert len(frames) == 1
        assert event_type.encode() in frames[0]
        assert b"build_start" not in frames[0]
    finally:
        await service.stop()
