from __future__ import annotations

import asyncio
import contextlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException
from langflow.api.v1.schemas import FlowDataRequest
from langflow.events.event_manager import create_default_event_manager
from langflow.services.job_queue.service import JobQueueService
from lfx.schema.schema import InputValueRequest


async def test_generate_flow_events_sanitizes_cooperative_and_queue_fallback_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both generate-flow error paths obey the caller-visible policy."""
    from langflow.api import build

    sensitive_detail = "owner-provider-secret"

    @contextlib.asynccontextmanager
    async def fake_session_scope():
        yield SimpleNamespace()

    monkeypatch.setattr(build, "session_scope", fake_session_scope)
    monkeypatch.setattr(build, "get_chat_service", lambda: SimpleNamespace())
    monkeypatch.setattr(
        build,
        "get_telemetry_service",
        lambda: SimpleNamespace(log_package_playground=AsyncMock()),
    )
    monkeypatch.setattr(
        build,
        "build_graph_from_data",
        AsyncMock(side_effect=RuntimeError(sensitive_detail)),
    )

    queue: asyncio.Queue = asyncio.Queue()
    event_manager = create_default_event_manager(queue)
    producer = build.generate_flow_events(
        flow_id=uuid4(),
        background_tasks=BackgroundTasks(),
        event_manager=event_manager,
        inputs=InputValueRequest(input_value="hello", session="delegate-session"),
        data=FlowDataRequest(nodes=[], edges=[]),
        files=None,
        stop_component_id=None,
        start_component_id=None,
        log_builds=False,
        current_user=SimpleNamespace(id=uuid4()),
        flow_name="shared-flow",
        expose_error_details=False,
    )

    with pytest.raises(HTTPException, match="Workflow execution failed") as exc_info:
        await JobQueueService._guarded_task("job-id", producer, event_manager, queue)
    assert exc_info.value.status_code == 500

    payloads: list[dict] = []
    saw_sentinel = False
    while not queue.empty():
        _event_id, value, _timestamp = queue.get_nowait()
        if value is None:
            saw_sentinel = True
            continue
        payloads.append(json.loads(value))

    error_payloads = [payload for payload in payloads if payload["event"] == "error"]
    assert error_payloads
    assert saw_sentinel
    assert all("Workflow execution failed." in json.dumps(payload) for payload in error_payloads)
    assert sensitive_detail not in json.dumps(payloads)
