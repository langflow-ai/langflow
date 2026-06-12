"""BackgroundExecutionService facade end-to-end over the default in-process backend.

Real JobService + real executor + real in-memory bus against the migrated test
DB. The frame source is injected (scripted) to stand in for a live graph build.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_settings_service

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.usefixtures("client")


def _frame(event_type: str, data: dict) -> tuple[bytes, str]:
    return (json.dumps({"event": event_type, "data": data}).encode("utf-8"), event_type)


async def _scripted_source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
    yield _frame("build_start", {})
    yield _frame("end_vertex", {"id": "n1"})
    yield _frame("end", {})


def _make_service() -> BackgroundExecutionService:
    return BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=lambda **_kw: _scripted_source,
    )


async def test_submit_creates_job_and_runs_to_completion(active_user):
    svc = _make_service()
    await svc.start()
    try:
        flow_id = uuid4()
        job_id = await svc.submit(flow_id=flow_id, request={"stream_protocol": "langflow"}, user=active_user)
        # Poll until terminal.
        st = None
        for _ in range(50):
            st = await svc.status(job_id, active_user)
            if st["status"] in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
                break
            await asyncio.sleep(0.05)
        assert st["status"] == JobStatus.COMPLETED
        # Durable result is surfaced on the status payload.
        assert st.get("result") is not None
    finally:
        await svc.stop()


async def test_events_reattach_replays_durable(active_user):
    svc = _make_service()
    await svc.start()
    try:
        job_id = await svc.submit(flow_id=uuid4(), request={"stream_protocol": "langflow"}, user=active_user)
        for _ in range(50):
            st = await svc.status(job_id, active_user)
            if st["status"] == JobStatus.COMPLETED:
                break
            await asyncio.sleep(0.05)
        # Reattach from 0 after completion: durable milestones replay, then end.
        seen = [chunk async for chunk in svc.events(job_id, last_event_id=None, user=active_user)]
        assert any(b"build_start" in c for c in seen)
        assert any(b"end_vertex" in c for c in seen)
    finally:
        await svc.stop()


async def test_events_polls_durable_log_for_cross_worker_job(active_user):
    # The job runs on ANOTHER worker, so this facade's live bus never sees its
    # frames. Durable job_events rows appear over time and the job goes terminal.
    # events() must replay them gap-free from the durable log and return, instead
    # of blocking forever on the empty local live queue.
    from langflow.services.deps import get_job_service

    job_service = get_job_service()
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=active_user.id)
    await job_service.update_job_status(job_id, JobStatus.IN_PROGRESS)
    await job_service.append_event(job_id, "build_start", {"event": "build_start", "data": {}})

    svc = _make_service()
    await svc.start()

    async def other_worker():
        await asyncio.sleep(0.3)
        await job_service.append_event(job_id, "end_vertex", {"event": "end_vertex", "data": {"id": "n1"}})
        await asyncio.sleep(0.3)
        await job_service.append_event(job_id, "end", {"event": "end", "data": {}})
        await job_service.set_result(job_id, {"ok": True})
        await job_service.update_job_status(job_id, JobStatus.COMPLETED, finished_timestamp=True)

    async def consume() -> list[bytes]:
        return [chunk async for chunk in svc.events(job_id, last_event_id=None, user=active_user)]

    worker = asyncio.create_task(other_worker())
    try:
        seen = await asyncio.wait_for(consume(), timeout=15)
    finally:
        await worker
        await svc.stop()

    assert any(b"build_start" in c for c in seen)
    assert any(b"end_vertex" in c for c in seen)
    assert any(b"end" in c for c in seen)


async def test_status_rejects_cross_user(active_user, user_two):
    # ``active_super_user`` shares ``active_user``'s username (and thus DB row),
    # so a genuinely distinct second user (``user_two``) is needed to exercise
    # the ownership check.
    svc = _make_service()
    await svc.start()
    try:
        job_id = await svc.submit(flow_id=uuid4(), request={"stream_protocol": "langflow"}, user=active_user)
        with pytest.raises(PermissionError):
            await svc.status(job_id, user_two)
    finally:
        await svc.stop()


async def test_submit_runs_in_process_when_job_queue_type_redis(active_user, monkeypatch):
    # With job_queue_type=redis the scaled backend is not shipped on this branch
    # (no redis_backend / worker modules). The facade must fall back to the
    # in-process executor, not raise ModuleNotFoundError building a scaled backend.
    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.settings, "job_queue_type", "redis")
    assert settings_service.settings.background_backend_is_scaled is True

    svc = BackgroundExecutionService(
        settings_service=settings_service,
        frame_source_factory=lambda **_kw: _scripted_source,
    )
    await svc.start()
    try:
        job_id = await svc.submit(flow_id=uuid4(), request={"stream_protocol": "langflow"}, user=active_user)
        st = None
        for _ in range(50):
            st = await svc.status(job_id, active_user)
            if st["status"] in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
                break
            await asyncio.sleep(0.05)
        assert st["status"] == JobStatus.COMPLETED
    finally:
        await svc.stop()


async def test_stop_cancels_job(active_user):
    gate = asyncio.Event()

    async def blocking_source(**_kwargs):
        yield _frame("build_start", {})
        await gate.wait()
        yield _frame("end", {})

    svc = BackgroundExecutionService(
        settings_service=get_settings_service(),
        frame_source_factory=lambda **_kw: blocking_source,
    )
    await svc.start()
    try:
        job_id = await svc.submit(flow_id=uuid4(), request={"stream_protocol": "langflow"}, user=active_user)
        await asyncio.sleep(0.1)
        await svc.stop_job(job_id, active_user)
        gate.set()
        st = None
        for _ in range(50):
            st = await svc.status(job_id, active_user)
            if st["status"] in {JobStatus.CANCELLED, JobStatus.FAILED, JobStatus.COMPLETED}:
                break
            await asyncio.sleep(0.05)
        assert st["status"] == JobStatus.CANCELLED
    finally:
        await svc.stop()
