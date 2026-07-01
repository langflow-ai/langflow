"""Tests for the v2 workflow endpoints on ``lfx serve`` (POST /workflows).

Real graph, no mocks: a ChatInput -> ChatOutput echo flow is registered and
exercised through the FastAPI app, asserting the v2 ``WorkflowExecutionResponse``
(sync) and the AG-UI / langflow SSE streams, plus the guard responses.
"""

import json

import pytest
from fastapi.testclient import TestClient
from lfx.cli.serve_app import FlowMeta, FlowRegistry, create_multi_serve_app
from lfx.cli.serve_workflow import _terminal_node_ids, _WorkflowEventQueue
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph

# WorkflowRunRequest requires flow_id to be a UUID (the v2 contract).
_FLOW_ID = "67ccd2be-17f0-4190-81ff-3bb2cf6508e6"
_MISSING_FLOW_ID = "00000000-0000-4000-8000-000000000000"
_API_KEY = "test-key"  # pragma: allowlist secret
_HEADERS = {"x-api-key": _API_KEY}


def _echo_graph() -> Graph:
    """A minimal real flow: ChatInput feeds its message straight to ChatOutput."""
    chat_input = ChatInput(_id="chat_input")
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response)
    graph = Graph(chat_input, chat_output)
    graph.prepare()
    return graph


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LANGFLOW_API_KEY", _API_KEY)
    registry = FlowRegistry()
    registry.add(
        _echo_graph(),
        FlowMeta(id=_FLOW_ID, relative_path=f"{_FLOW_ID}.json", title="echo", description=None),
    )
    app = create_multi_serve_app(registry=registry)
    with TestClient(app) as test_client:
        yield test_client


def test_sync_returns_workflow_execution_response(client):
    resp = client.post(
        "/workflows",
        json={"flow_id": _FLOW_ID, "input_value": "hello", "mode": "sync"},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["flow_id"] == _FLOW_ID
    assert body["output"]["reason"] == "single"
    assert "hello" in (body["output"]["text"] or "")
    # The full per-component map is present alongside the primary answer.
    assert body["outputs"]


def test_stream_agui_emits_run_lifecycle_and_content(client):
    resp = client.post(
        "/workflows",
        json={"flow_id": _FLOW_ID, "input_value": "hello", "mode": "stream", "stream_protocol": "agui"},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert "RUN_STARTED" in body
    assert "RUN_FINISHED" in body
    assert "hello" in body


def test_stream_langflow_protocol_passes_through_frames(client):
    resp = client.post(
        "/workflows",
        json={"flow_id": _FLOW_ID, "input_value": "hello", "mode": "stream", "stream_protocol": "langflow"},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert "data:" in body
    assert "hello" in body


def test_unknown_stream_protocol_422(client):
    resp = client.post(
        "/workflows",
        json={"flow_id": _FLOW_ID, "mode": "stream", "stream_protocol": "bogus"},
        headers=_HEADERS,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "UNKNOWN_STREAM_PROTOCOL"


def test_unsupported_fields_rejected_422(client):
    resp = client.post(
        "/workflows",
        json={"flow_id": _FLOW_ID, "input_value": "x", "tweaks": {"ChatOutput-x": {"foo": 1}}},
        headers=_HEADERS,
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "LFX_SERVE_UNSUPPORTED_FIELDS"
    assert "tweaks" in detail["fields"]


def test_background_mode_rejected_422(client):
    resp = client.post(
        "/workflows",
        json={"flow_id": _FLOW_ID, "input_value": "x", "mode": "background"},
        headers=_HEADERS,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "LFX_SERVE_UNSUPPORTED_MODE"


def test_unknown_flow_404(client):
    resp = client.post(
        "/workflows",
        json={"flow_id": _MISSING_FLOW_ID, "input_value": "x"},
        headers=_HEADERS,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "FLOW_NOT_FOUND"


def test_missing_api_key_401(client):
    resp = client.post("/workflows", json={"flow_id": _FLOW_ID, "input_value": "x"})
    assert resp.status_code == 401


def test_globals_accepted(client):
    """Request-level globals are applied, not rejected (backend v2 parity)."""
    resp = client.post(
        "/workflows",
        json={"flow_id": _FLOW_ID, "input_value": "hello", "mode": "sync", "globals": {"MY_VAR": "v"}},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["flow_id"] == _FLOW_ID


def test_unknown_output_ids_rejected_422(client):
    """Unknown output_ids are a 422 up front, before running (backend v2 parity)."""
    resp = client.post(
        "/workflows",
        json={"flow_id": _FLOW_ID, "input_value": "x", "mode": "sync", "output_ids": ["does-not-exist"]},
        headers=_HEADERS,
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "UNKNOWN_OUTPUT_IDS"
    assert "does-not-exist" in detail["message"]


def test_valid_output_ids_accepted(client):
    """A real terminal node id is accepted and runs to completion."""
    terminal_ids = _terminal_node_ids(_echo_graph())
    resp = client.post(
        "/workflows",
        json={"flow_id": _FLOW_ID, "input_value": "hello", "mode": "sync", "output_ids": terminal_ids},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text


async def test_stream_event_queue_overflow_emits_error():
    """A full queue (slow client) surfaces an explicit error frame, not a silent drop."""
    queue = _WorkflowEventQueue(maxsize=1)
    queue.put_nowait(("a", b'{"event": "token"}', 0.0))  # fills the queue
    queue.put_nowait(("b", b'{"event": "token"}', 0.0))  # overflow -> triggers the error task

    first = await queue.get()
    assert first[0] == "a"

    err_id, err_val, _ = await queue.get()
    assert err_id.startswith("error-")
    assert json.loads(err_val.decode("utf-8"))["event"] == "error"

    sentinel = await queue.get()
    assert sentinel[0] is None
    assert sentinel[1] is None

    # Once overflowed the queue drops further puts instead of unbounded growth.
    queue.put_nowait(("c", b"{}", 0.0))
    await queue.aclose()
