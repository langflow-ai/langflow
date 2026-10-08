"""A client disconnect must cancel the lfx stream's run task exactly once.

Starlette streams a response inside an AnyIO task group. On a server that speaks
ASGI HTTP spec < 2.4 (uvicorn advertises 2.3) it answers ``http.disconnect`` by
cancelling that task group's scope, and AnyIO delivers that cancellation
level-triggered: until the response task leaves the cancelled scope, it is
cancelled again on every event-loop tick. ``stream_workflow_frames`` used to
cancel its run task in ``finally`` and then ``await`` it inside that scope.
asyncio forwards a cancel of a task that is awaiting another task to the awaited
task, so the run received one cancel per tick and any component's cleanup could
be cut short at its next ``await``.

These tests drive the real generator through a real ``StreamingResponse`` with a
uvicorn-shaped scope, so the cancellation arrives exactly as it does live.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

from lfx.workflow import router as workflow_router
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
from lfx.workflow.converters import ParsedWorkflowRun
from starlette.responses import StreamingResponse

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

    async def run_with_cleanup(self) -> None:
        """Block until cancelled, then clean up over several awaits (a DB write, a client close)."""
        self.task = asyncio.current_task()
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancels += 1
            raise
        finally:
            for _ in range(_CLEANUP_STEPS):
                await asyncio.sleep(0.01)
                self.cleanup_steps_done += 1

    async def run_counting_cancels(self) -> None:
        """Like ``run_with_cleanup``, but counts (and survives) any cancel that lands during cleanup."""
        self.task = asyncio.current_task()
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancels += 1
            raise
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


def _patch_run(monkeypatch, run) -> None:
    async def fake_execute_graph_with_capture(_graph, _input_value, **_kwargs) -> None:
        await run()

    monkeypatch.setattr(workflow_router, "execute_graph_with_capture", fake_execute_graph_with_capture)


async def _stream_until_disconnect(component: _Component) -> float:
    """Serve the stream the way uvicorn does, disconnect once the component runs; return the wait."""
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id="run-1", thread_id="thread-1"))
    parsed = ParsedWorkflowRun(flow_id="flow-1", input_value="", mode="stream")
    response = StreamingResponse(workflow_router.stream_workflow_frames(SimpleNamespace(context={}), parsed, adapter))

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
    _patch_run(monkeypatch, component.run_counting_cancels)

    await _stream_until_disconnect(component)

    assert component.cancels == 1
    assert component.cleanup_steps_done == _CLEANUP_STEPS


async def test_disconnect_lets_a_component_finish_its_multi_await_cleanup(monkeypatch):
    component = _Component()
    _patch_run(monkeypatch, component.run_with_cleanup)

    await _stream_until_disconnect(component)

    assert component.cancels == 1
    assert component.cleanup_steps_done == _CLEANUP_STEPS
    assert component.task is not None
    assert component.task.cancelled()


async def test_disconnect_stops_waiting_for_a_run_that_ignores_cancellation(monkeypatch):
    component = _Component()
    _patch_run(monkeypatch, component.run_ignoring_cancel)
    monkeypatch.setattr(workflow_router, "RUN_CANCEL_GRACE_SECONDS", 0.1)

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


async def test_closing_the_stream_cancels_the_run_task_once(monkeypatch):
    """A consumer that closes the generator (GeneratorExit, no AnyIO scope) gets the same single cancel."""
    component = _Component()
    _patch_run(monkeypatch, component.run_counting_cancels)
    # The agui adapter opens with RUN_STARTED, so the first frame arrives without the run emitting.
    adapter = get_stream_adapter("agui", StreamAdapterContext(run_id="run-1", thread_id="thread-1"))
    parsed = ParsedWorkflowRun(flow_id="flow-1", input_value="", mode="stream")
    stream = workflow_router.stream_workflow_frames(SimpleNamespace(context={}), parsed, adapter)

    await stream.__anext__()
    await component.started.wait()
    await stream.aclose()

    assert component.cancels == 1
    assert component.cleanup_steps_done == _CLEANUP_STEPS
