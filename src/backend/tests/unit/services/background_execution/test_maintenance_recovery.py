"""Queued startup work survives maintenance changes without restarting the API."""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest
from langflow.api.utils import migration_pause
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_job_service, get_settings_service, session_scope
from langflow.services.maintenance.state import set_maintenance

pytestmark = pytest.mark.usefixtures("client")


async def _set_paused(*, enabled):
    async with session_scope() as session:
        await set_maintenance(session, enabled=enabled)


async def _finished(job_id):
    async with asyncio.timeout(4):
        while (await get_job_service().get_job_by_job_id(job_id)).status != JobStatus.COMPLETED:  # noqa: ASYNC110
            await asyncio.sleep(0.02)


async def _frames(**_kwargs):
    yield json.dumps({"event": "end", "data": {}}).encode(), "end"


async def test_queued_startup_work_resumes_when_maintenance_starts_between_rows(active_user, monkeypatch):
    jobs = get_job_service()
    first, second = uuid4(), uuid4()
    for job_id in (first, second):
        await jobs.create_job(job_id=job_id, flow_id=uuid4(), user_id=active_user.id)
    service = BackgroundExecutionService(get_settings_service(), frame_source_factory=lambda **_kw: _frames)
    enqueue = service._enqueue
    dispatched = []

    async def enqueue_then_pause(**kwargs):
        await enqueue(**kwargs)
        dispatched.append(kwargs["job_id"])
        if len(dispatched) == 1:
            await _finished(kwargs["job_id"])
            await _set_paused(enabled=True)

    monkeypatch.setattr(service, "_enqueue", enqueue_then_pause)
    try:
        await service.sweep_orphans_on_startup()
        remaining = next(job_id for job_id in (first, second) if job_id not in dispatched)
        assert (await jobs.get_job_by_job_id(remaining)).status == JobStatus.QUEUED
        await _set_paused(enabled=False)
        await _finished(remaining)
        assert len(dispatched) == 2
    finally:
        await _set_paused(enabled=False)
        await service.stop()


async def test_maintenance_reenabled_during_recovery_does_not_drop_startup_work(active_user, monkeypatch):
    jobs = get_job_service()
    job_id = uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid4(), user_id=active_user.id)
    service = BackgroundExecutionService(get_settings_service(), frame_source_factory=lambda **_kw: _frames)
    original_paused = migration_pause.writes_paused
    toggled = asyncio.Event()

    async def pause_again_after_recovery_observes_unpaused():
        paused = await original_paused()
        if not paused and not toggled.is_set() and asyncio.current_task() is service._maintenance_recovery_task:
            # Reproduce the real gap between the recovery poll and its next sweep.
            await _set_paused(enabled=True)
            toggled.set()
        return paused

    monkeypatch.setattr(migration_pause, "writes_paused", pause_again_after_recovery_observes_unpaused)
    try:
        await _set_paused(enabled=True)
        await service.sweep_orphans_on_startup()
        recovery = service._maintenance_recovery_task
        await _set_paused(enabled=False)
        await asyncio.wait_for(toggled.wait(), timeout=4)
        # Its re-entered sweep must observe the new pause before it is cleared.
        await asyncio.wait_for(recovery, timeout=4)
        assert (await jobs.get_job_by_job_id(job_id)).status == JobStatus.QUEUED
        await _set_paused(enabled=False)
        await _finished(job_id)
    finally:
        await _set_paused(enabled=False)
        await service.stop()
