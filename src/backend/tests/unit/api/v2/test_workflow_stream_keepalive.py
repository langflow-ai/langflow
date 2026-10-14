"""Transport keepalives preserve idle live streams without entering workflow events."""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
from lfx.workflow.converters import ParsedWorkflowRun

_UVICORN_SCOPE = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}}
_KEEPALIVE = b": keepalive\n\n"


def _patch_run(monkeypatch, run):
    from langflow.api.v2 import workflow_execution
    from langflow.services import deps

    telemetry = SimpleNamespace(log_package_run=AsyncMock())
    monkeypatch.setattr(workflow_execution, "generate_flow_events", run)
    monkeypatch.setattr(workflow_execution, "_STREAM_KEEPALIVE_INTERVAL_SECONDS", 0.01, raising=False)
    monkeypatch.setattr(deps, "get_telemetry_service", lambda: telemetry)
    return workflow_execution, telemetry


def _response(workflow_execution, protocol):
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
    return [
        json.loads(line.removeprefix("data: "))
        for frame in frames
        for line in frame.decode().splitlines()
        if line.startswith("data: ")
    ]


@pytest.mark.parametrize("protocol", ["langflow", "agui"])
@pytest.mark.parametrize("fail", [False, True])
async def test_idle_live_stream_emits_comments_and_preserves_terminal_events(monkeypatch, protocol, fail):
    release = asyncio.Event()

    async def run(*, event_manager, **_kwargs):
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
        if message["type"] == "http.response.body" and message.get("body"):
            bodies.append(message["body"])
            if bodies.count(_KEEPALIVE) == 2:
                release.set()

    async def receive():
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
    async def run(*, event_manager, **_kwargs):
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
    heartbeat_sent = asyncio.Event()
    cleanup_done = asyncio.Event()
    cancelled = []

    async def run(**_kwargs):
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
        if message.get("body") == _KEEPALIVE:
            heartbeat_sent.set()

    async def receive():
        await heartbeat_sent.wait()
        return {"type": "http.disconnect"}

    await asyncio.wait_for(_response(workflow_execution, protocol)(_UVICORN_SCOPE, receive, send), timeout=2)

    assert cancelled == [True]
    assert cleanup_done.is_set()
    telemetry.log_package_run.assert_not_awaited()


@pytest.mark.parametrize("protocol", ["langflow", "agui"])
async def test_background_frame_source_has_no_transport_comments(monkeypatch, protocol):
    async def run(*, event_manager, **_kwargs):
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
