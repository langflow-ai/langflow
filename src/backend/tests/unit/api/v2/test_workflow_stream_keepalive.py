"""Transport keepalives preserve idle live streams without entering workflow events."""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, Request
from lfx.schema.workflow import PublicWorkflowRunRequest
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
from lfx.workflow.converters import ParsedWorkflowRun

_UVICORN_SCOPE = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}}
_KEEPALIVE = b": keepalive\n\n"


def _patch_run(monkeypatch, run):
    """Replace only the graph runner and telemetry, and shorten idle deadlines."""
    from langflow.api.v2 import workflow_execution
    from langflow.services import deps

    telemetry = SimpleNamespace(log_package_run=AsyncMock())
    monkeypatch.setattr(workflow_execution, "generate_flow_events", run)
    monkeypatch.setattr(workflow_execution, "_STREAM_KEEPALIVE_INTERVAL_SECONDS", 0.01, raising=False)
    monkeypatch.setattr(deps, "get_telemetry_service", lambda: telemetry)
    return workflow_execution, telemetry


def _response(workflow_execution, protocol):
    """Build the authenticated live response with the requested stream adapter."""
    flow_id = uuid4()
    return workflow_execution._execute_streaming_workflow(
        adapter=get_stream_adapter(protocol, StreamAdapterContext(run_id="run", thread_id="thread")),
        run_id="run",
        parsed=ParsedWorkflowRun(flow_id=str(flow_id), input_value="", mode="stream"),
        flow=SimpleNamespace(id=flow_id, name="flow", user_id=uuid4()),
        current_user=SimpleNamespace(id=uuid4()),
        background_tasks=BackgroundTasks(),
    )


def _payloads(frames):
    """Decode data events while ignoring transport comments."""
    return [
        json.loads(line.removeprefix("data: "))
        for frame in frames
        for line in frame.decode().splitlines()
        if line.startswith("data: ")
    ]


@pytest.mark.parametrize("protocol", ["langflow", "agui"])
@pytest.mark.parametrize("fail", [False, True])
async def test_idle_live_stream_emits_comments_and_preserves_terminal_events(monkeypatch, protocol, fail):
    """Idle comments leave protocol terminal events and sequential IDs intact."""
    release = asyncio.Event()

    async def run(*, event_manager, **_kwargs):
        """Hold the source until two comments arrive, then finish or fail."""
        await release.wait()
        if fail:
            msg = "component failed"
            raise RuntimeError(msg)
        event_manager.send_event(event_type="end", data={})
        await event_manager.queue.put((None, None, time.time()))

    workflow_execution, _telemetry = _patch_run(monkeypatch, run)
    response = _response(workflow_execution, protocol)
    bodies = []

    async def send(message):
        """Capture ASGI output and release the idle runner after two comments."""
        if message["type"] == "http.response.body" and message.get("body"):
            bodies.append(message["body"])
            if bodies.count(_KEEPALIVE) == 2:
                release.set()

    async def receive():
        """Keep the client connected until the workflow ends."""
        await asyncio.Event().wait()

    await asyncio.wait_for(response(_UVICORN_SCOPE, receive, send), timeout=2)

    assert bodies.count(_KEEPALIVE) >= 2
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    events = _payloads(bodies)
    if protocol == "agui":
        assert events[-1]["type"] == ("RUN_ERROR" if fail else "RUN_FINISHED")
    else:
        assert events[-1]["event"] == ("error" if fail else "end")
    ids = [
        int(line.removeprefix("id: "))
        for frame in bodies
        for line in frame.decode().splitlines()
        if line.startswith("id: ")
    ]
    assert ids == list(range(len(ids)))


@pytest.mark.parametrize("protocol", ["langflow", "agui"])
async def test_active_live_stream_does_not_insert_keepalives(monkeypatch, protocol):
    """Already queued events stream without extra comments."""

    async def run(*, event_manager, **_kwargs):
        """Complete immediately with several data events."""
        for chunk in range(5):
            event_manager.send_event(event_type="token", data={"chunk": str(chunk)})
        event_manager.send_event(event_type="end", data={})
        await event_manager.queue.put((None, None, time.time()))

    workflow_execution, _telemetry = _patch_run(monkeypatch, run)
    monkeypatch.setattr(workflow_execution, "_STREAM_KEEPALIVE_INTERVAL_SECONDS", 15.0)
    frames = [frame async for frame in _response(workflow_execution, protocol).body_iterator]

    assert _KEEPALIVE not in frames
    assert _payloads(frames)


@pytest.mark.parametrize("protocol", ["langflow", "agui"])
async def test_disconnect_after_keepalive_cancels_run_once_and_finishes_cleanup(monkeypatch, protocol):
    """Disconnecting an idle response allows the run's cleanup to finish."""
    heartbeat_sent = asyncio.Event()
    cleanup_done = asyncio.Event()
    cancelled = []

    async def run(**_kwargs):
        """Count cancellations and perform cleanup across several awaits."""
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        finally:
            for _ in range(5):
                await asyncio.sleep(0)
            cleanup_done.set()

    workflow_execution, telemetry = _patch_run(monkeypatch, run)

    async def send(message):
        """Signal the first transport comment."""
        if message.get("body") == _KEEPALIVE:
            heartbeat_sent.set()

    async def receive():
        """Disconnect after the first transport comment."""
        await heartbeat_sent.wait()
        return {"type": "http.disconnect"}

    await asyncio.wait_for(_response(workflow_execution, protocol)(_UVICORN_SCOPE, receive, send), timeout=2)

    assert cancelled == [True]
    assert cleanup_done.is_set()
    telemetry.log_package_run.assert_not_awaited()


@pytest.mark.parametrize("protocol", ["langflow", "agui"])
async def test_background_frame_source_has_no_transport_comments(monkeypatch, protocol):
    """The internal frame source remains free of HTTP transport comments."""

    async def run(*, event_manager, **_kwargs):
        """Hold the internal source beyond the transport deadline."""
        await asyncio.sleep(0.04)
        event_manager.send_event(event_type="end", data={})
        await event_manager.queue.put((None, None, time.time()))

    workflow_execution, _telemetry = _patch_run(monkeypatch, run)
    frames = [
        frame
        async for frame, _event_type in workflow_execution._stream_event_frames(
            adapter=get_stream_adapter(protocol, StreamAdapterContext(run_id="run", thread_id="thread")),
            flow_id=uuid4(),
            flow_name="flow",
            background_tasks=BackgroundTasks(),
            parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="", mode="background"),
            current_user=SimpleNamespace(id=uuid4()),
            protocol="v2.background",
            execution_family="workflow_v2",
            emit_output_capture=True,
            execution_timeout=None,
        )
    ]

    assert all(not frame.startswith(b":") for frame in frames)
    assert _payloads(frames)


@pytest.fixture
async def public_response(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Create a real public flow and build its response through the public handler."""
    from langflow.api.v2.workflow_public import execute_public_workflow

    from tests.unit.build_utils import create_flow

    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    response = await client.patch(f"api/v1/flows/{flow_id}", json={"access_type": "PUBLIC"}, headers=logged_in_headers)
    assert response.status_code == 200

    async def build(protocol):
        """Pass the public admission checks before constructing the SSE response."""
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v2/workflows/public",
                "scheme": "http",
                "server": ("testserver", 80),
                "headers": [(b"cookie", b"client_id=keepalive-visitor")],
            }
        )
        return await execute_public_workflow(
            PublicWorkflowRunRequest(flow_id=str(flow_id), input_value="", stream_protocol=protocol),
            BackgroundTasks(),
            request,
        )

    return build


async def _collect_idle_response(response, release):
    """Serve an ASGI response until two keepalives release its source."""
    bodies = []

    async def send(message):
        """Capture each body and release the source after two idle deadlines."""
        if message["type"] == "http.response.body" and message.get("body"):
            bodies.append(message["body"])
            if bodies.count(_KEEPALIVE) == 2:
                release.set()

    async def receive():
        """Keep the client connected until the source finishes."""
        await asyncio.Event().wait()

    await asyncio.wait_for(response(_UVICORN_SCOPE, receive, send), timeout=2)
    return bodies


@pytest.mark.parametrize("protocol", ["langflow", "agui"])
@pytest.mark.parametrize("fail", [False, True])
async def test_idle_public_stream_emits_comments_and_preserves_terminal_events(
    monkeypatch, public_response, protocol, fail
):
    """The public SSE boundary keeps idle runs alive in both wire protocols."""
    release = asyncio.Event()

    async def run(*, event_manager, **_kwargs):
        """Finish or fail after the transport proves it remains connected."""
        await release.wait()
        if fail:
            msg = "component failed"
            raise RuntimeError(msg)
        event_manager.send_event(event_type="end", data={})
        await event_manager.queue.put((None, None, time.time()))

    _patch_run(monkeypatch, run)
    response = await public_response(protocol)
    bodies = await _collect_idle_response(response, release)

    assert bodies.count(_KEEPALIVE) >= 2
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _payloads(bodies)
    if protocol == "agui":
        assert events[-1]["type"] == ("RUN_ERROR" if fail else "RUN_FINISHED")
    else:
        assert events[-1]["event"] == ("error" if fail else "end")
    ids = [
        int(line.removeprefix("id: "))
        for frame in bodies
        for line in frame.decode().splitlines()
        if line.startswith("id: ")
    ]
    assert ids == list(range(len(ids)))


@pytest.mark.parametrize("protocol", ["langflow", "agui"])
async def test_public_disconnect_after_keepalive_finishes_run_cleanup(monkeypatch, public_response, protocol):
    """A public visitor disconnect cancels the run once and completes cleanup."""
    heartbeat_sent = asyncio.Event()
    cleanup_done = asyncio.Event()
    cancelled = []

    async def run(**_kwargs):
        """Keep the public run idle, then unwind over several awaits."""
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        finally:
            for _ in range(5):
                await asyncio.sleep(0)
            cleanup_done.set()

    _workflow_execution, telemetry = _patch_run(monkeypatch, run)
    response = await public_response(protocol)

    async def send(message):
        """Signal that an idle public response delivered its first comment."""
        if message.get("body") == _KEEPALIVE:
            heartbeat_sent.set()

    async def receive():
        """Disconnect after the first public response keepalive."""
        await heartbeat_sent.wait()
        return {"type": "http.disconnect"}

    await asyncio.wait_for(response(_UVICORN_SCOPE, receive, send), timeout=2)

    assert cancelled == [True]
    assert cleanup_done.is_set()
    telemetry.log_package_run.assert_not_awaited()


async def _reattach_response(monkeypatch, events):
    """Build the reattach response with a controllable background event source."""
    from langflow.api.v2 import workflow

    job_id = uuid4()
    current_user = SimpleNamespace(id=uuid4(), is_superuser=False)

    async def status(requested_job, requested_user):
        """Verify the ownership pre-check receives the requested job and caller."""
        assert requested_job == job_id
        assert requested_user is current_user

    async def get_job_by_job_id(requested_job, *, user_id):
        """Return a caller-owned job without an end-user scope."""
        assert requested_job == job_id
        assert user_id == current_user.id
        return SimpleNamespace(job_metadata={})

    def source(requested_job, *, last_event_id, user):
        """Preserve the durable cursor when subscribing to the source."""
        assert requested_job == job_id
        assert last_event_id == "7"
        assert user is current_user
        return events

    monkeypatch.setattr(
        workflow, "get_background_execution_service", lambda: SimpleNamespace(status=status, events=source)
    )
    monkeypatch.setattr(workflow, "get_job_service", lambda: SimpleNamespace(get_job_by_job_id=get_job_by_job_id))
    request = Request({"type": "http", "headers": [(b"last-event-id", b"7")]})
    return await workflow.reattach_workflow_events(str(job_id), request, current_user)


async def test_idle_reattach_stream_preserves_durable_frames_and_ids(monkeypatch):
    """Reattach keepalives leave durable replay bytes and resumed event IDs intact."""
    from langflow.api.v2 import workflow_execution

    release = asyncio.Event()
    closed = asyncio.Event()
    replay = b'id: 8\nevent: token\ndata: {"chunk":"replayed"}\n\n'
    terminal = b"id: 9\nevent: end\ndata: {}\n\n"

    async def events():
        """Replay one durable frame, then hold the live tail until released."""
        try:
            yield replay
            await release.wait()
            yield terminal
        finally:
            closed.set()

    monkeypatch.setattr(workflow_execution, "_STREAM_KEEPALIVE_INTERVAL_SECONDS", 0.01)
    response = await _reattach_response(monkeypatch, events())
    bodies = await _collect_idle_response(response, release)

    assert bodies.count(_KEEPALIVE) >= 2
    assert [frame for frame in bodies if frame != _KEEPALIVE] == [replay, terminal]
    assert closed.is_set()


async def test_reattach_disconnect_closes_idle_subscription_once(monkeypatch):
    """Closing an idle reattach response completes event subscription cleanup."""
    from langflow.api.v2 import workflow_execution

    heartbeat_sent = asyncio.Event()
    cleanup_done = asyncio.Event()
    cancelled = []

    async def events():
        """Stand in for an idle subscription with cleanup across multiple awaits."""
        try:
            await asyncio.Event().wait()
            yield b"unreachable"
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        finally:
            for _ in range(5):
                await asyncio.sleep(0)
            cleanup_done.set()

    monkeypatch.setattr(workflow_execution, "_STREAM_KEEPALIVE_INTERVAL_SECONDS", 0.01)
    response = await _reattach_response(monkeypatch, events())

    async def send(message):
        """Signal the first idle subscription comment."""
        if message.get("body") == _KEEPALIVE:
            heartbeat_sent.set()

    async def receive():
        """Disconnect the reattach client after its first keepalive."""
        await heartbeat_sent.wait()
        return {"type": "http.disconnect"}

    await asyncio.wait_for(response(_UVICORN_SCOPE, receive, send), timeout=2)

    assert cancelled == [True]
    assert cleanup_done.is_set()
