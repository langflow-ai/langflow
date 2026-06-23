"""Tests for the v2 workflow endpoints on ``lfx serve`` (POST /workflows).

Real graph, no mocks: a ChatInput -> ChatOutput echo flow is registered and
exercised through the FastAPI app, asserting the v2 ``WorkflowExecutionResponse``
(sync) and the AG-UI / langflow SSE streams, plus the guard responses.
"""

import pytest
from fastapi.testclient import TestClient
from lfx.cli.serve_app import FlowMeta, FlowRegistry, create_multi_serve_app
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
