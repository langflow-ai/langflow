"""Runner: persist durable frames, publish all frames, finalize terminal state.

Uses the real JobService against the test DB (via the ``client`` fixture, which
brings up the migrated app DB) and the real in-memory live bus. No mocking of
our own code: the frame source is a scripted async generator standing in for
the v1 build loop, which is legitimate test input, not a mock of our logic.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from langflow.api.v2.adapters import StreamAdapterContext, get_stream_adapter
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.runner import JobRunner
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_job_service

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.usefixtures("client")


def _frame(event_type: str, data: dict) -> tuple[bytes, str]:
    payload = {"event": event_type, "data": data}
    return (json.dumps(payload).encode("utf-8"), event_type)


async def _make_job(flow_id, user_id):
    job_id = uuid4()
    await get_job_service().create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)
    return job_id


async def test_runner_persists_durable_frames_only(active_user):
    job_service = get_job_service()
    flow_id = uuid4()
    job_id = await _make_job(flow_id, active_user.id)

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})  # durable
        yield _frame("token", {"chunk": "hi"})  # ephemeral
        yield _frame("end_vertex", {"id": "n1"})  # durable
        yield _frame("end", {})  # durable

    bus = InMemoryLiveBus()
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(job_service=job_service, live_bus=bus, adapter=adapter, frame_source=source)

    await runner.run(job_id=job_id, source_kwargs={})

    events = await job_service.read_events(job_id, after_seq=0)
    persisted_types = [e.event_type for e in events]
    # token is ephemeral -> not persisted; the rest are durable.
    assert "token" not in persisted_types
    assert "build_start" in persisted_types
    assert "end_vertex" in persisted_types
    # seqs are contiguous and increasing
    assert [e.seq for e in events] == sorted(e.seq for e in events)


async def test_runner_finalizes_completed(active_user):
    job_service = get_job_service()
    job_id = await _make_job(uuid4(), active_user.id)

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("end", {})

    bus = InMemoryLiveBus()
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(job_service=job_service, live_bus=bus, adapter=adapter, frame_source=source)

    await runner.run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED


async def test_runner_finalizes_failed_and_writes_error(active_user):
    job_service = get_job_service()
    job_id = await _make_job(uuid4(), active_user.id)

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("error", {"error": "kaboom"})

    bus = InMemoryLiveBus()
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(job_service=job_service, live_bus=bus, adapter=adapter, frame_source=source)

    await runner.run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.FAILED
    assert job.error is not None


async def test_runner_timeout_writes_terminal_event_and_error(active_user):
    """TIMED_OUT must write an error blob AND a terminal job_events row (design §8)."""
    job_service = get_job_service()
    job_id = await _make_job(uuid4(), active_user.id)

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        # Run past the job timeout so asyncio.wait_for raises TimeoutError.
        await asyncio.sleep(5)
        yield _frame("end", {})

    bus = InMemoryLiveBus()
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(job_service=job_service, live_bus=bus, adapter=adapter, frame_source=source, job_timeout=0.2)

    await asyncio.wait_for(runner.run(job_id=job_id, source_kwargs={}), timeout=10)

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.TIMED_OUT
    # Error blob is populated on timeout (was NULL before the fix).
    assert job.error is not None
    assert job.error.get("type") == "timed_out"
    # A terminal milestone is on the durable log.
    events = await job_service.read_events(job_id)
    assert any(e.event_type == "run_timed_out" for e in events)


async def test_runner_cancel_writes_terminal_event(active_user):
    """CANCELLED must write a terminal job_events row (design §8)."""
    job_service = get_job_service()
    job_id = await _make_job(uuid4(), active_user.id)

    from langflow.services.database.models.jobs.model import SignalType

    gate = asyncio.Event()

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        await gate.wait()
        yield _frame("end_vertex", {"id": "n1"})
        yield _frame("end", {})

    bus = InMemoryLiveBus()
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(job_service=job_service, live_bus=bus, adapter=adapter, frame_source=source)

    run_task = asyncio.create_task(runner.run(job_id=job_id, source_kwargs={}))
    await asyncio.sleep(0.1)
    await job_service.write_signal(job_id, SignalType.STOP)
    gate.set()
    await asyncio.wait_for(run_task, timeout=5)

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.CANCELLED
    events = await job_service.read_events(job_id)
    assert any(e.event_type == "run_cancelled" for e in events)


async def test_late_stop_after_completion_clears_result(active_user):
    """A stop reconciled to CANCELLED after a genuine completion must not keep result."""
    job_service = get_job_service()
    job_id = await _make_job(uuid4(), active_user.id)

    from langflow.services.database.models.jobs.model import SignalType

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        # The flow completes cleanly (set_result + COMPLETED), but a STOP lands in
        # the race window before the runner's terminal reconcile.
        await job_service.write_signal(job_id, SignalType.STOP)
        yield _frame("end", {})

    bus = InMemoryLiveBus()
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(job_service=job_service, live_bus=bus, adapter=adapter, frame_source=source)

    await runner.run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    # Stop wins over the racing completion...
    assert job.status == JobStatus.CANCELLED
    # ...and the terminal state is internally consistent: no completed result blob.
    assert job.result is None
    assert (job.error or {}).get("type") == "cancelled"


async def test_runner_stops_at_signal_boundary(active_user):
    job_service = get_job_service()
    job_id = await _make_job(uuid4(), active_user.id)

    gate = asyncio.Event()

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        yield _frame("build_start", {})
        # Block until the test writes a STOP signal, then yield one more frame
        # so the runner's boundary poll observes the signal.
        await gate.wait()
        yield _frame("end_vertex", {"id": "n1"})
        yield _frame("end", {})

    bus = InMemoryLiveBus()
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(job_service=job_service, live_bus=bus, adapter=adapter, frame_source=source)

    run_task = asyncio.create_task(runner.run(job_id=job_id, source_kwargs={}))
    await asyncio.sleep(0.1)
    from langflow.services.database.models.jobs.model import SignalType

    await job_service.write_signal(job_id, SignalType.STOP)
    gate.set()
    await asyncio.wait_for(run_task, timeout=5)

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.CANCELLED
