"""Regression tests for SSE keepalive emission during idle workflow runs (#15178).

When a flow node runs longer than an idle proxy's connection timeout (commonly
50-60s for ALB, nginx-ingress, corporate firewalls), the SSE stream went silent
and the middlebox silently killed the connection. The backend kept running and
often completed the run, but the UI saw a generic "network error".

Fix: emit an SSE comment line (``: keepalive\\n\\n``) every
``STREAM_KEEPALIVE_INTERVAL_SEC`` seconds while the queue is empty. SSE comments
are ignored by EventSource clients and by the buffer task, so this is wire-safe.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import BackgroundTasks
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
from lfx.workflow.converters import ParsedWorkflowRun


async def test_stream_emits_keepalive_when_queue_is_idle(monkeypatch):
    """During a long-running node the stream must emit periodic SSE comment
    frames so idle proxies do not silently kill the connection.
    """
    from langflow.api.v2 import workflow_execution as wf_exec
    from langflow.services import deps

    async def fake_generate_flow_events(**_kwargs):
        # Simulate a long-running node: never send any events, never put the
        # sentinel. The streaming loop will hit queue.get() timeouts repeatedly
        # and emit keepalive frames.
        await asyncio.sleep(60)

    telemetry = SimpleNamespace(log_package_run=AsyncMock())
    monkeypatch.setattr(wf_exec, "generate_flow_events", fake_generate_flow_events)
    monkeypatch.setattr(deps, "get_telemetry_service", lambda: telemetry)

    # Shorten the keepalive interval for the test so we don't wait 15s.
    monkeypatch.setattr(wf_exec, "STREAM_KEEPALIVE_INTERVAL_SEC", 0.05)

    adapter = get_stream_adapter(
        "langflow",
        StreamAdapterContext(run_id="keepalive-job", thread_id="keepalive-thread"),
    )

    async def _consume_briefly():
        gen = wf_exec._stream_event_frames(
            adapter=adapter,
            flow_id=uuid4(),
            flow_name="flow",
            background_tasks=BackgroundTasks(),
            parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="", mode="stream"),
            current_user=SimpleNamespace(id=uuid4()),
            run_id="keepalive-job",
            protocol="langflow",
            execution_family="workflow_v2",
        )
        frames: list[bytes] = []
        try:
            async for frame, _event_type in gen:
                frames.append(frame)
                if sum(1 for f in frames if f == wf_exec._KEEPALIVE_FRAME) >= 3:
                    break
        finally:
            await gen.aclose()
        return frames

    # Bound the test so a regression does not hang the suite.
    frames = await asyncio.wait_for(_consume_briefly(), timeout=2.0)

    keepalives = [f for f in frames if f == wf_exec._KEEPALIVE_FRAME]
    assert len(keepalives) >= 3, (
        f"expected >=3 keepalive frames within 2s, got {len(keepalives)}; "
        "regression for #15178 - SSE stream no longer emits idle keepalive"
    )
    # SSE comment is exactly ": keepalive\n\n".
    assert wf_exec._KEEPALIVE_FRAME == b": keepalive\n\n"


async def test_stream_does_not_emit_keepalive_during_active_traffic(monkeypatch):
    """If events arrive faster than the keepalive interval, no keepalive is
    needed (and emitting one would just inflate the wire).
    """
    from langflow.api.v2 import workflow_execution as wf_exec
    from langflow.services import deps

    async def fake_generate_flow_events(**kwargs):
        # Send 5 events back-to-back, each well under the keepalive interval,
        # then the sentinel.
        em = kwargs["event_manager"]
        for i in range(5):
            em.send_event(event_type="token", data={"chunk": f"tok-{i}"})
        await em.queue.put((None, None, time.time()))

    telemetry = SimpleNamespace(log_package_run=AsyncMock())
    monkeypatch.setattr(wf_exec, "generate_flow_events", fake_generate_flow_events)
    monkeypatch.setattr(deps, "get_telemetry_service", lambda: telemetry)
    monkeypatch.setattr(wf_exec, "STREAM_KEEPALIVE_INTERVAL_SEC", 0.5)

    adapter = get_stream_adapter(
        "langflow",
        StreamAdapterContext(run_id="active-job", thread_id="active-thread"),
    )

    frames: list[bytes] = []
    async for frame, _event_type in wf_exec._stream_event_frames(
        adapter=adapter,
        flow_id=uuid4(),
        flow_name="flow",
        background_tasks=BackgroundTasks(),
        parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="", mode="stream"),
        current_user=SimpleNamespace(id=uuid4()),
        run_id="active-job",
        protocol="langflow",
        execution_family="workflow_v2",
    ):
        frames.append(frame)

    keepalives = [f for f in frames if f == wf_exec._KEEPALIVE_FRAME]
    assert keepalives == [], f"expected zero keepalive frames during bursty traffic, got {len(keepalives)}"
