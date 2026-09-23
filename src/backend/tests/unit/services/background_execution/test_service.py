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
    # Why: these tests isolate the service/runner plumbing (submit, status, dedupe, cross-user
    # ownership, terminal handling) from graph execution. The REAL frame source
    # (generate_flow_events over a live graph) is exercised end-to-end in test_build_pause_seam.
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
        # Why: a bare task cancel makes execute_with_status write FAILED before the
        # runner's shielded finally reconciles the pending STOP to CANCELLED. That
        # FAILED is a transient intermediate state, not the settled outcome — so
        # poll for the reconciled terminal status instead of the first terminal one.
        for _ in range(50):
            st = await svc.status(job_id, active_user)
            if st["status"] == JobStatus.CANCELLED:
                break
            await asyncio.sleep(0.05)
        assert st["status"] == JobStatus.CANCELLED
    finally:
        await svc.stop()


async def test_retention_sweep_is_opt_in(monkeypatch):
    """No retention window configured means no sweep task at all.

    Retention deletes run history, so it stays off until an operator sets a
    window: a default deployment must spawn no purge loop.
    """
    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.settings, "background_retention_days", 0)

    svc = BackgroundExecutionService(settings_service, frame_source_factory=lambda **_kw: _scripted_source)
    await svc.start()
    try:
        assert svc._retention_task is None
    finally:
        await svc.stop()


async def test_retention_sweep_starts_when_a_window_is_set(monkeypatch):
    """A configured window starts the periodic purge, and stop() tears it down."""
    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.settings, "background_retention_days", 30)

    svc = BackgroundExecutionService(settings_service, frame_source_factory=lambda **_kw: _scripted_source)
    await svc.start()
    try:
        assert svc._retention_task is not None
        assert not svc._retention_task.done()
    finally:
        await svc.stop()
    assert svc._retention_task is None


class _TickCounter:
    """Stands in for the service module's ``random``: counts sweep ticks, skips the wait.

    The retention loop draws its jitter exactly once per tick, so counting draws tells
    a batch purged inside one tick apart from one purged on the next tick.
    """

    def __init__(self) -> None:
        self.ticks = 0

    def uniform(self, _low: float, _high: float) -> float:
        self.ticks += 1
        return 0.0


class _ScriptedPurges:
    """A job service whose purge replays scripted outcomes, then parks until cancelled."""

    def __init__(self, ticks: _TickCounter, outcomes: list[int | Exception]) -> None:
        self._ticks = ticks
        self._outcomes = iter(outcomes)
        self.calls: list[tuple[int, int | str]] = []
        self.exhausted = asyncio.Event()

    async def purge_terminal_jobs(self, *, older_than_days: float, limit: int) -> int:  # noqa: ARG002
        outcome = next(self._outcomes, None)
        if outcome is None:
            self.exhausted.set()
            await asyncio.Event().wait()
        if isinstance(outcome, Exception):
            self.calls.append((self._ticks.ticks, "raised"))
            raise outcome
        self.calls.append((self._ticks.ticks, outcome))
        return outcome


class _RecordingLogger:
    def __init__(self) -> None:
        self.exceptions: list[str] = []

    async def aexception(self, msg: str, *_args, **_kwargs) -> None:
        self.exceptions.append(msg)


async def _run_scripted_sweep(monkeypatch, outcomes: list[int | Exception]) -> tuple[_ScriptedPurges, _RecordingLogger]:
    from langflow.services.background_execution import service as service_module

    ticks = _TickCounter()
    purges = _ScriptedPurges(ticks, outcomes)
    recording_logger = _RecordingLogger()
    monkeypatch.setattr(service_module, "random", ticks)
    monkeypatch.setattr(service_module, "get_job_service", lambda: purges)
    monkeypatch.setattr(service_module, "logger", recording_logger)
    monkeypatch.setattr(get_settings_service().settings, "background_retention_days", 7)

    svc = _make_service()
    svc._start_retention_sweep()
    try:
        await asyncio.wait_for(purges.exhausted.wait(), timeout=5)
    finally:
        await svc.stop()
    return purges, recording_logger


async def test_retention_sweep_drains_a_backlog_within_one_tick(monkeypatch):
    """Full batches keep the tick going; the first short batch ends it.

    Enabling retention on an install with a large backlog must catch up in a few
    ticks, not one batch an hour.
    """
    from langflow.services.background_execution.service import _RETENTION_BATCH_SIZE

    purges, _ = await _run_scripted_sweep(monkeypatch, [_RETENTION_BATCH_SIZE, _RETENTION_BATCH_SIZE, 3, 0])

    assert purges.calls == [(1, _RETENTION_BATCH_SIZE), (1, _RETENTION_BATCH_SIZE), (1, 3), (2, 0)]


async def test_retention_sweep_logs_a_failed_pass_and_runs_the_next_tick(monkeypatch):
    """A purge that raises is logged loudly, and the loop survives to try again."""
    purges, recording_logger = await _run_scripted_sweep(monkeypatch, [RuntimeError("database unavailable"), 0])

    assert purges.calls == [(1, "raised"), (2, 0)]
    assert recording_logger.exceptions == ["Background job retention sweep failed"]


async def test_retention_sweep_purges_real_rows_and_spares_live_work(monkeypatch):
    """End to end over the real job store: aged terminal rows go, live rows stay."""
    from datetime import datetime, timedelta, timezone

    from langflow.services.background_execution import service as service_module
    from langflow.services.database.models.jobs.model import Job, JobType
    from langflow.services.deps import get_job_service, session_scope
    from sqlmodel import update

    job_service = get_job_service()
    aged = datetime.now(timezone.utc) - timedelta(days=90)

    async def _aged_job(status: JobStatus):
        job_id = uuid4()
        await job_service.create_job(job_id=job_id, flow_id=uuid4(), job_type=JobType.WORKFLOW, user_id=uuid4())
        async with session_scope() as session:
            await session.exec(
                update(Job).where(Job.job_id == job_id).values(status=status, created_timestamp=aged)  # type: ignore[call-overload]
            )
        return job_id

    terminal = [await _aged_job(JobStatus.COMPLETED) for _ in range(3)]
    suspended = await _aged_job(JobStatus.SUSPENDED)

    monkeypatch.setattr(service_module, "_RETENTION_INTERVAL_S", 0.01)
    monkeypatch.setattr(service_module, "_RETENTION_BATCH_SIZE", 2)
    monkeypatch.setattr(get_settings_service().settings, "background_retention_days", 30)
    svc = _make_service()
    svc._start_retention_sweep()
    try:
        for _ in range(100):
            if all([await job_service.get_job_by_job_id(job_id) is None for job_id in terminal]):
                break
            await asyncio.sleep(0.05)
    finally:
        await svc.stop()

    assert [job_id for job_id in terminal if await job_service.get_job_by_job_id(job_id) is not None] == []
    assert (await job_service.get_job_by_job_id(suspended)).status == JobStatus.SUSPENDED
