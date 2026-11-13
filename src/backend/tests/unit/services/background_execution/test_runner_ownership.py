"""A runner that loses its lease must not mutate the winning execution."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.background_execution.runner import JobRunner
from langflow.services.database.models.jobs.model import ExecutionSignal, Job, JobEvent, JobStatus, SignalType
from langflow.services.jobs import service as jobs_module
from langflow.services.jobs.exceptions import HUMAN_INPUT_REQUIRED_EVENT
from langflow.services.jobs.service import JobService
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
async def jobs(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ownership.db'}")
    async with engine.begin() as connection:
        for model in (Job, JobEvent, ExecutionSignal):
            await connection.run_sync(model.__table__.create)

    @asynccontextmanager
    async def session_scope():
        async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
            yield session

    monkeypatch.setattr(jobs_module, "session_scope", session_scope)
    try:
        yield JobService()
    finally:
        await engine.dispose()


class _RecordingBus:
    def __init__(self):
        self.closed = []

    async def publish(self, _job_id, _frame):
        pass

    async def close(self, job_id):
        self.closed.append(job_id)


def _runner(jobs, job_id, source, *, owner=None):
    bus = _RecordingBus()
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="ownership"))
    return JobRunner(job_service=jobs, live_bus=bus, adapter=adapter, frame_source=source, owner=owner), bus


@pytest.mark.parametrize("stop_requested", [False, True])
async def test_rejected_runner_leaves_terminal_events_and_stop_signal_untouched(jobs, stop_requested):
    job_id = uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid4())
    await jobs.update_job_status(job_id, JobStatus.TIMED_OUT, finished_timestamp=True)
    await jobs.append_event(job_id, "run_timed_out", {"type": "timed_out"})
    if stop_requested:
        await jobs.write_signal(job_id, SignalType.STOP)

    async def never_runs(**_kwargs):
        msg = "A rejected runner must not execute the graph"
        raise AssertionError(msg)
        yield b"", "end"

    runner, bus = _runner(jobs, job_id, never_runs)
    await runner.run(job_id=job_id, source_kwargs={})

    assert (await jobs.get_job_by_job_id(job_id)).status == JobStatus.TIMED_OUT
    assert [event.event_type for event in await jobs.read_events(job_id)] == ["run_timed_out"]
    assert [signal.signal_type for signal in await jobs.unconsumed_signals(job_id)] == (
        [SignalType.STOP] if stop_requested else []
    )
    assert bus.closed == []


async def test_rejected_runner_does_not_consume_the_current_owners_stop(jobs):
    job_id = uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid4())
    await jobs.update_job_status(job_id, JobStatus.IN_PROGRESS)
    await jobs.update_job_metadata(job_id, {"owner": "worker:b"})
    await jobs.write_signal(job_id, SignalType.STOP)

    async def never_runs(**_kwargs):
        msg = "The rejected owner must not execute the graph"
        raise AssertionError(msg)
        yield b"", "end"

    runner, bus = _runner(jobs, job_id, never_runs, owner="worker:a")
    await runner.run(job_id=job_id, source_kwargs={})

    job = await jobs.get_job_by_job_id(job_id)
    assert job.status == JobStatus.IN_PROGRESS
    assert job.job_metadata["owner"] == "worker:b"
    assert [signal.signal_type for signal in await jobs.unconsumed_signals(job_id)] == [SignalType.STOP]
    assert await jobs.read_events(job_id) == []
    assert bus.closed == []


@pytest.mark.parametrize("lost_to", ["failed", "reclaimed"])
async def test_late_pause_does_not_change_a_job_after_ownership_is_lost(jobs, lost_to):
    job_id = uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid4())
    await jobs.update_job_metadata(job_id, {"owner": "worker:a"})

    async def late_pause(**_kwargs):
        if lost_to == "failed":
            await jobs.fail_in_progress_job(job_id, error={"type": "worker_lost"})
        else:
            await jobs.update_job_metadata(job_id, {"owner": "worker:b"})
        yield json.dumps({"request_id": "too-late"}).encode(), HUMAN_INPUT_REQUIRED_EVENT

    runner, bus = _runner(jobs, job_id, late_pause, owner="worker:a")
    await runner.run(job_id=job_id, source_kwargs={})

    job = await jobs.get_job_by_job_id(job_id)
    assert job.status == (JobStatus.FAILED if lost_to == "failed" else JobStatus.IN_PROGRESS)
    assert "pending_request_id" not in job.job_metadata
    assert await jobs.read_events(job_id) == []
    assert bus.closed == []


@pytest.mark.parametrize("terminal_write_fails", [False, True])
async def test_suspend_failure_does_not_fail_a_new_owner(jobs, monkeypatch, terminal_write_fails):
    job_id = uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid4())
    await jobs.update_job_metadata(job_id, {"owner": "worker:a"})

    async def unavailable_suspend(_job_id, _metadata, **_kwargs):
        await jobs.update_job_metadata(job_id, {"owner": "worker:b"})
        await jobs.write_signal(job_id, SignalType.STOP)
        msg = "The suspend transaction could not commit"
        raise ConnectionError(msg)

    monkeypatch.setattr(jobs, "suspend_job", unavailable_suspend)
    if terminal_write_fails:

        async def unavailable_terminal_write(*_args, **_kwargs):
            msg = "The terminal transaction could not commit"
            raise ConnectionError(msg)

        monkeypatch.setattr(jobs, "terminalize_live_job", unavailable_terminal_write)

    async def pause(**_kwargs):
        yield json.dumps({"request_id": "uncommitted"}).encode(), HUMAN_INPUT_REQUIRED_EVENT

    runner, bus = _runner(jobs, job_id, pause, owner="worker:a")
    await runner.run(job_id=job_id, source_kwargs={})

    job = await jobs.get_job_by_job_id(job_id)
    assert job.status == JobStatus.IN_PROGRESS
    assert job.job_metadata["owner"] == "worker:b"
    assert job.error is None
    assert await jobs.read_events(job_id) == []
    assert [signal.signal_type for signal in await jobs.unconsumed_signals(job_id)] == [SignalType.STOP]
    assert bus.closed == []


async def test_heartbeat_loss_stops_the_graph_without_finalizing_the_new_owner(jobs, monkeypatch):
    job_id = uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid4())
    await jobs.update_job_metadata(job_id, {"owner": "worker:a"})
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def lose_lease(_job_id, _owner):
        await started.wait()
        await jobs.update_job_metadata(job_id, {"owner": "worker:b"})
        return False

    monkeypatch.setattr(jobs, "heartbeat", lose_lease)

    async def blocked_graph(**_kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
        yield b"", "end"

    runner, bus = _runner(jobs, job_id, blocked_graph, owner="worker:a")
    await asyncio.wait_for(runner.run(job_id=job_id, source_kwargs={}), timeout=2)

    assert stopped.is_set()
    job = await jobs.get_job_by_job_id(job_id)
    assert job.status == JobStatus.IN_PROGRESS
    assert job.job_metadata["owner"] == "worker:b"
    assert job.error is None
    assert await jobs.read_events(job_id) == []
    assert bus.closed == []


async def test_suspension_waits_for_an_in_flight_heartbeat_to_settle(jobs, monkeypatch):
    job_id = uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid4())
    await jobs.update_job_metadata(job_id, {"owner": "worker:a"})
    renewing = asyncio.Event()
    finish_renewal = asyncio.Event()
    settled = asyncio.Event()
    stopping = asyncio.Event()
    real_suspend = jobs.suspend_job

    async def pending_heartbeat(_job_id, _owner):
        renewing.set()
        await finish_renewal.wait()
        settled.set()
        return True

    async def suspend_after_renewal(*args, **kwargs):
        assert settled.is_set(), "Suspension must not race an abandoned heartbeat transaction"
        return await real_suspend(*args, **kwargs)

    monkeypatch.setattr(jobs, "heartbeat", pending_heartbeat)
    monkeypatch.setattr(jobs, "suspend_job", suspend_after_renewal)

    async def pause(**_kwargs):
        await renewing.wait()
        yield json.dumps({"request_id": "after-renewal"}).encode(), HUMAN_INPUT_REQUIRED_EVENT

    runner, bus = _runner(jobs, job_id, pause, owner="worker:a")
    real_stop_heartbeat = runner._stop_heartbeat

    async def observe_stop(task):
        stopping.set()
        await real_stop_heartbeat(task)

    monkeypatch.setattr(runner, "_stop_heartbeat", observe_stop)
    task = asyncio.create_task(runner.run(job_id=job_id, source_kwargs={}))
    try:
        await asyncio.wait_for(stopping.wait(), timeout=2)
        finish_renewal.set()
        await asyncio.wait_for(task, timeout=2)
    finally:
        finish_renewal.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert (await jobs.get_job_by_job_id(job_id)).status == JobStatus.SUSPENDED
    assert settled.is_set()
    assert bus.closed == []


async def _reclaim_after_a_successful_heartbeat(jobs, job_id):
    """Exercise the real retry and claim transitions after A's lease expires."""
    stale = datetime.now(timezone.utc) - timedelta(minutes=5)
    async with jobs_module.session_scope() as session:
        job = await session.get(Job, job_id)
        job.job_metadata = {**job.job_metadata, "heartbeat_at": stale.isoformat()}
        job.lease_heartbeat_at = stale
        session.add(job)
    assert await jobs.retry_requeue_claim(job_id, expected_attempt=1)
    assert await jobs.claim_queued_lease(job_id, owner="worker:b", lease_ttl_s=45)
    assert await jobs.begin_live_job(job_id, owner="worker:b")


@pytest.mark.parametrize("source_exit", ["end", "cancel"])
async def test_accepted_runner_does_not_consume_a_reclaiming_owners_stop(jobs, monkeypatch, source_exit):
    job_id = uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid4())
    await jobs.update_job_metadata(job_id, {"owner": "worker:a", "attempt": 1})
    renewed = asyncio.Event()
    heartbeat = jobs.heartbeat

    async def first_heartbeat(*args):
        result = await heartbeat(*args)
        assert result is True
        renewed.set()
        return result

    monkeypatch.setattr(jobs, "heartbeat", first_heartbeat)

    async def stale_source(**_kwargs):
        await renewed.wait()
        await _reclaim_after_a_successful_heartbeat(jobs, job_id)
        await jobs.write_signal(job_id, SignalType.STOP)
        if source_exit == "cancel":
            reason = "LANGFLOW_USER_CANCELLED"
            raise asyncio.CancelledError(reason)
        if False:
            yield b"", "end"

    runner, bus = _runner(jobs, job_id, stale_source, owner="worker:a")
    await runner.run(job_id=job_id, source_kwargs={})

    job = await jobs.get_job_by_job_id(job_id)
    assert job.status == JobStatus.IN_PROGRESS
    assert job.job_metadata["owner"] == "worker:b"
    assert [signal.signal_type for signal in await jobs.unconsumed_signals(job_id)] == [SignalType.STOP]
    assert await jobs.read_events(job_id) == []
    assert bus.closed == []


@pytest.mark.parametrize(
    ("new_status", "event_type"),
    [(JobStatus.TIMED_OUT, "run_timed_out"), (JobStatus.CANCELLED, "run_cancelled")],
)
async def test_accepted_runner_does_not_finalize_a_new_owners_terminal_status(
    jobs, monkeypatch, new_status, event_type
):
    job_id = uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid4())
    await jobs.update_job_metadata(job_id, {"owner": "worker:a", "attempt": 1})
    renewed = asyncio.Event()
    heartbeat = jobs.heartbeat

    async def first_heartbeat(*args):
        result = await heartbeat(*args)
        assert result is True
        renewed.set()
        return result

    monkeypatch.setattr(jobs, "heartbeat", first_heartbeat)

    async def stale_source(**_kwargs):
        await renewed.wait()
        await _reclaim_after_a_successful_heartbeat(jobs, job_id)
        assert await jobs.terminalize_live_job(job_id, new_status, owner="worker:b", error={"type": "winner"})
        await jobs.append_event(job_id, event_type, {"type": "winner"})
        msg = "The old execution exits after its replacement has finished"
        raise RuntimeError(msg)
        yield b"", "end"

    runner, bus = _runner(jobs, job_id, stale_source, owner="worker:a")
    await runner.run(job_id=job_id, source_kwargs={})

    job = await jobs.get_job_by_job_id(job_id)
    assert job.status == new_status
    assert job.error == {"type": "winner"}
    assert [(event.event_type, event.payload) for event in await jobs.read_events(job_id)] == [
        (event_type, {"type": "winner"})
    ]
    assert bus.closed == []


@pytest.mark.parametrize("replacement", ["new_owner", "worker_lost"])
@pytest.mark.parametrize("payload_kind", ["result", "error"])
async def test_accepted_runner_does_not_replace_payload_after_losing_its_job(
    jobs, monkeypatch, replacement, payload_kind
):
    job_id = uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid4())
    await jobs.update_job_metadata(job_id, {"owner": "worker:a", "attempt": 1})
    renewed = asyncio.Event()
    heartbeat = jobs.heartbeat

    async def first_heartbeat(*args):
        result = await heartbeat(*args)
        assert result is True
        renewed.set()
        return result

    monkeypatch.setattr(jobs, "heartbeat", first_heartbeat)

    async def stale_source(**_kwargs):
        await renewed.wait()
        if replacement == "new_owner":
            await _reclaim_after_a_successful_heartbeat(jobs, job_id)
        else:
            assert await jobs.fail_in_progress_job(job_id, error={"type": "worker_lost"})
        if payload_kind == "error":
            yield json.dumps({"event": "error", "data": {"type": "stale_error"}}).encode(), "error"

    runner, bus = _runner(jobs, job_id, stale_source, owner="worker:a")
    await runner.run(job_id=job_id, source_kwargs={})

    job = await jobs.get_job_by_job_id(job_id)
    assert job.status == (JobStatus.IN_PROGRESS if replacement == "new_owner" else JobStatus.FAILED)
    assert job.result is None
    assert job.error == (None if replacement == "new_owner" else {"type": "worker_lost"})
    assert bus.closed == []
