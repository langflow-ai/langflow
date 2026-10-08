"""A client disconnect must cancel a v2 workflow stream's run task exactly once.

The Playground streams ``POST /api/v2/workflows`` over SSE. Starlette serves that
response inside an AnyIO task group and, on a server that speaks ASGI HTTP spec
< 2.4 (uvicorn advertises 2.3), answers ``http.disconnect`` by cancelling the task
group's scope. AnyIO delivers that cancellation level-triggered: until the
response task leaves the cancelled scope, it is cancelled again on every
event-loop tick. ``_stream_event_frames`` used to cancel its run task in
``finally`` and then ``await`` it inside that scope. asyncio forwards a cancel of
a task that is awaiting another task to the awaited task, so the run received a
cancel per tick: every running component's cleanup could be cut short, and
``JobService.execute_with_status`` could lose its FAILED write and leave the
WORKFLOW job row IN_PROGRESS.

These tests serve the real ``EventSourceResponse`` from ``build_stream_response``
with a uvicorn-shaped scope, so the cancellation arrives exactly as it does live.
Only ``generate_flow_events`` (the build loop) is replaced by a stand-in component.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks
from lfx.schema.workflow import JobStatus
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
from lfx.workflow.converters import ParsedWorkflowRun

# uvicorn's HTTP protocols advertise this spec version, which puts Starlette on the
# task-group path that cancels the response scope on disconnect.
_UVICORN_SCOPE = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}}
_CLEANUP_STEPS = 5
# A component that ignores cancellation gives up on its own after this long, so a
# regression fails the timing assertion instead of hanging the suite.
_SWALLOWER_GIVES_UP_AFTER = 5.0


class _Component:
    """Stands in for a component that is mid-run when the client disconnects."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancels = 0
        self.cleanup_steps_done = 0
        self.task: asyncio.Task | None = None

    async def block_until_cancelled(self) -> None:
        self.task = asyncio.current_task()
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancels += 1
            raise

    async def run_with_cleanup(self) -> None:
        """Block until cancelled, then clean up over several awaits (a DB write, a client close)."""
        try:
            await self.block_until_cancelled()
        finally:
            for _ in range(_CLEANUP_STEPS):
                await asyncio.sleep(0.01)
                self.cleanup_steps_done += 1

    async def run_counting_cancels(self) -> None:
        """Like ``run_with_cleanup``, but counts (and survives) any cancel that lands during cleanup."""
        try:
            await self.block_until_cancelled()
        finally:
            for _ in range(_CLEANUP_STEPS):
                try:
                    await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    self.cancels += 1
                self.cleanup_steps_done += 1

    async def run_ignoring_cancel(self) -> None:
        """Swallow every cancel and keep working until released."""
        self.task = asyncio.current_task()
        self.started.set()
        deadline = time.monotonic() + _SWALLOWER_GIVES_UP_AFTER
        while not self.release.is_set() and time.monotonic() < deadline:
            try:
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                self.cancels += 1


def _patch_build_loop(monkeypatch, run) -> None:
    from langflow.api.v2 import workflow as workflow_api
    from langflow.api.v2 import workflow_execution as wf_exec
    from langflow.services import deps

    async def fake_generate_flow_events(**_kwargs) -> None:
        await run()

    monkeypatch.setattr(workflow_api, "_apply_execution_gates", lambda parsed, *_args: parsed)
    monkeypatch.setattr(wf_exec, "generate_flow_events", fake_generate_flow_events)
    monkeypatch.setattr(deps, "get_telemetry_service", lambda: SimpleNamespace(log_package_run=AsyncMock()))


async def _stream_until_disconnect(component: _Component) -> float:
    """Serve the stream the way uvicorn does, disconnect once the component runs; return the wait."""
    from langflow.api.v2 import workflow as workflow_api

    flow_id = uuid4()
    response = workflow_api.build_stream_response(
        ParsedWorkflowRun(flow_id=str(flow_id), input_value="", mode="stream"),
        SimpleNamespace(id=flow_id, name="flow", user_id=uuid4()),
        SimpleNamespace(id=uuid4()),
        stream_protocol="agui",
        background_tasks=BackgroundTasks(),
    )

    async def receive() -> dict:
        await component.started.wait()
        return {"type": "http.disconnect"}

    async def send(_message: dict) -> None:
        return None

    started_at = time.monotonic()
    await response(_UVICORN_SCOPE, receive, send)
    return time.monotonic() - started_at


async def test_disconnect_cancels_the_run_task_once(monkeypatch):
    component = _Component()
    _patch_build_loop(monkeypatch, component.run_counting_cancels)

    await _stream_until_disconnect(component)

    assert component.cancels == 1
    assert component.cleanup_steps_done == _CLEANUP_STEPS


async def test_disconnect_lets_a_component_finish_its_multi_await_cleanup(monkeypatch):
    component = _Component()
    _patch_build_loop(monkeypatch, component.run_with_cleanup)

    await _stream_until_disconnect(component)

    assert component.cancels == 1
    assert component.cleanup_steps_done == _CLEANUP_STEPS
    assert component.task is not None
    assert component.task.cancelled()


async def test_disconnect_lets_the_job_row_reach_failed(monkeypatch):
    """``execute_with_status`` must finish its FAILED write instead of leaving the row IN_PROGRESS."""
    from langflow.services.jobs.service import JobService

    component = _Component()
    written: list[JobStatus] = []

    async def update_job_status(_job_id, status, **_kwargs) -> None:
        # A real write awaits the session more than once (begin, flush, commit).
        for _ in range(3):
            await asyncio.sleep(0.01)
        written.append(status)

    job_service = SimpleNamespace(update_job_status=update_job_status)

    async def run_as_tracked_job() -> None:
        # The build loop wraps a live run in execute_with_status (see generate_flow_events).
        await JobService.execute_with_status(job_service, uuid4(), component.block_until_cancelled)

    _patch_build_loop(monkeypatch, run_as_tracked_job)

    await _stream_until_disconnect(component)

    assert component.cancels == 1
    assert written == [JobStatus.IN_PROGRESS, JobStatus.FAILED]


async def test_disconnect_stops_waiting_for_a_run_that_ignores_cancellation(monkeypatch):
    from langflow.api.v2 import workflow_execution as wf_exec

    component = _Component()
    _patch_build_loop(monkeypatch, component.run_ignoring_cancel)
    monkeypatch.setattr(wf_exec, "RUN_CANCEL_GRACE_SECONDS", 0.1)

    try:
        waited = await _stream_until_disconnect(component)

        # The response task gives up after the grace period instead of being pinned
        # until the component finishes, and it never cancels the run a second time.
        assert waited < _SWALLOWER_GIVES_UP_AFTER / 2
        assert component.cancels == 1
        assert component.task is not None
        assert not component.task.done()
    finally:
        component.release.set()
        if component.task is not None:
            await asyncio.wait({component.task}, timeout=_SWALLOWER_GIVES_UP_AFTER)


async def test_cancelling_a_plain_asyncio_consumer_cancels_the_run_task_once(monkeypatch):
    """The background runner iterates the frames in a plain task; one cancel of it reaches the run once."""
    from langflow.api.v2 import workflow_execution as wf_exec

    component = _Component()
    _patch_build_loop(monkeypatch, component.run_counting_cancels)
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id="run-1", thread_id="thread-1"))

    async def consume() -> None:
        async for _frame in wf_exec._stream_event_frames(
            adapter=adapter,
            flow_id=uuid4(),
            flow_name="flow",
            background_tasks=BackgroundTasks(),
            parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="", mode="stream"),
            current_user=SimpleNamespace(id=uuid4()),
            run_id="run-1",
            protocol="v2",
            execution_family="workflow_v2",
        ):
            pass

    consumer = asyncio.create_task(consume())
    await component.started.wait()
    consumer.cancel()

    with pytest.raises(asyncio.CancelledError):
        await consumer
    assert component.cancels == 1
    assert component.cleanup_steps_done == _CLEANUP_STEPS
