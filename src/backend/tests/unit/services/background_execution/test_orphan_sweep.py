"""Startup orphan sweep: re-enqueue QUEUED, fail orphaned IN_PROGRESS."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_job_service, get_settings_service

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.usefixtures("client")


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
