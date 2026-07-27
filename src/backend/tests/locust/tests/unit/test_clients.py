"""Unit tests for Locust protocol lifecycle clients."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.locust.langflow_runtime.clients.mcp_streamable import McpStreamableClient
from tests.locust.langflow_runtime.clients.sse import SseEvent, SseOverflowError, SseTruncationError, parse_sse_events
from tests.locust.langflow_runtime.clients.webhooks import correlate_webhook_events
from tests.locust.langflow_runtime.clients.workflows import classify_workflow_status_response
from tests.locust.langflow_runtime.config.naming import metric_name


def _line_iter(lines: list[str]):
    yield from lines


def test_parse_sse_events_multiframe() -> None:
    lines = [
        ": heartbeat",
        "event: connected",
        "data: {}",
        "",
        "event: end",
        'data: {"ok": true}',
        "",
    ]
    events = list(parse_sse_events(_line_iter(lines)))
    assert [event.event for event in events] == ["connected", "end"]
    assert events[1].data == '{"ok": true}'


def test_parse_sse_events_truncation_when_terminal_required() -> None:
    with pytest.raises(SseTruncationError):
        list(
            parse_sse_events(
                _line_iter(["event: connected", "data: {}", ""]),
                terminal_events={"end"},
            )
        )


def test_parse_sse_events_overflow() -> None:
    lines = ["event: tick", "data: 1", "", "event: tick", "data: 2", ""]
    with pytest.raises(SseOverflowError):
        list(parse_sse_events(_line_iter(lines), max_events=1))


def test_mcp_jsonrpc_id_increment() -> None:
    class FakeHttp:
        def post(self, _url: str, **kwargs: Any) -> Any:
            return type(
                "Resp",
                (),
                {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "text": json.dumps({"jsonrpc": "2.0", "id": kwargs["json"]["id"], "result": {}}),
                },
            )()

    from tests.locust.langflow_runtime.clients.base import ApiClient

    client = McpStreamableClient(
        api=ApiClient.from_locust(
            FakeHttp(),
            base_url="http://localhost:7860",
            api_key="test-key",  # pragma: allowlist secret
        ),
        project_id="00000000-0000-4000-8000-000000000001",
    )
    first = client._build_request("initialize", params={"protocolVersion": "x"})
    second = client._build_request("tools/list", params={})
    assert first["id"] == 1
    assert second["id"] == 2
    assert first["jsonrpc"] == "2.0"
    assert "id" not in client._build_request("notifications/initialized", is_notification=True)


def test_workflow_terminal_classification_408() -> None:
    body = {
        "detail": {
            "error": "Execution timeout",
            "code": "EXECUTION_TIMEOUT",
            "message": "Workflow execution timed out",
            "job_id": "00000000-0000-4000-8000-000000000099",
        }
    }
    status = classify_workflow_status_response(408, body)
    assert status.terminal is True
    assert status.success is False
    assert status.status == "timed_out"


def test_workflow_terminal_classification_500_job_failed() -> None:
    body = {
        "detail": {
            "error": "Job failed",
            "code": "JOB_FAILED",
            "message": "Job failed execution.",
            "job_id": "00000000-0000-4000-8000-000000000099",
        }
    }
    status = classify_workflow_status_response(500, body)
    assert status.terminal is True
    assert status.success is False
    assert status.status == "failed"


def test_workflow_active_status_200() -> None:
    status = classify_workflow_status_response(200, {"status": "in_progress", "job_id": "abc"})
    assert status.terminal is False
    assert status.status == "in_progress"


def test_workflow_sync_uses_httpx_transport_without_internal_kwargs() -> None:
    import httpx

    from tests.locust.langflow_runtime.clients.base import ApiClient
    from tests.locust.langflow_runtime.clients.workflows import WorkflowsClient

    observed: dict[str, Any] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        observed.update(json.loads(request.content))
        return httpx.Response(200, json={"outputs": [{"outputs": {"message": {"message": "ok"}}}]})

    transport = httpx.MockTransport(handle)
    with httpx.Client(transport=transport) as http:
        client = WorkflowsClient(
            api=ApiClient.from_httpx(http, base_url="http://example.test", api_key="test-key"),
        )
        result = client.run_sync(flow_id="flow-1", input_value="hello", session_id="session-1")

    assert observed == {
        "flow_id": "flow-1",
        "input_value": "hello",
        "mode": "sync",
        "stream_protocol": "langflow",
        "session_id": "session-1",
    }
    assert result["outputs"][0]["outputs"]["message"]["message"] == "ok"


def test_parse_sse_events_records_timing() -> None:
    from tests.locust.langflow_runtime.clients.sse import SseTimingStats

    lines = [
        "event: connected",
        "data: {}",
        "",
        "event: end",
        "data: {}",
        "",
    ]
    timing = SseTimingStats()
    events = list(parse_sse_events(_line_iter(lines), timing=timing))
    assert [event.event for event in events] == ["connected", "end"]
    assert timing.first_event_s is not None
    assert timing.inter_event_s is not None
    assert len(timing.inter_event_s) == 1


def test_correlate_webhook_events() -> None:
    events = [
        SseEvent(event="connected", data="{}"),
        SseEvent(event="end", data="{}"),
    ]
    correlation = correlate_webhook_events(events, accepted=True)
    assert correlation.connected is True
    assert correlation.accepted is True
    assert correlation.completed is True
    assert correlation.terminal_event == "end"


def test_metric_name_format() -> None:
    assert metric_name("mcp", "tools_call", "protocol_calibration", "passthrough") == (
        "mcp:tools_call:protocol_calibration:passthrough"
    )
