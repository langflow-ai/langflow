"""Cross-host contract test for the shared v2 workflow router.

No mocks: a real ``WorkflowHostBase`` subclass returns a real ``ResolvedFlow``
built from a real 2-node connected ``Graph`` (ChatInput -> ChatOutput), mounted
on a bare ``FastAPI()`` with ``TestClient``. The asserted surface is the lfx
router itself, so the langflow host (which substitutes real DB-backed resolvers)
inherits the exact same wire/SSE/gating contract.
"""

import json
from copy import deepcopy
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx.schema.workflow import (
    JobStatus,
    WorkflowExecutionResponse,
    WorkflowJobResponse,
    WorkflowStopResponse,
)
from lfx.workflow.actions import WorkflowAction
from lfx.workflow.host import ResolvedFlow, WorkflowHost, WorkflowHostBase
from lfx.workflow.router import create_workflow_router

_FLOW_ID = "67ccd2be-17f0-4190-81ff-3bb2cf6508e6"


def _echo_graph() -> Graph:
    """A minimal real flow: ChatInput feeds its message straight to ChatOutput."""
    chat_input = ChatInput(_id="chat_input")
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response)
    graph = Graph(chat_input, chat_output)
    graph.prepare()
    return graph


class _FakeHost(WorkflowHostBase):
    """Real (non-mock) no-db host returning a real ResolvedFlow.

    Records the action passed to ``authorize`` so the test can assert the router
    hands over a ``WorkflowAction`` member, not a raw string.
    """

    def __init__(self, graph: Graph, *, supports_background: bool = False) -> None:
        self._graph = graph
        self.supports_background = supports_background
        self.authorized_actions: list[Any] = []

    async def resolve_caller(self, request: Request) -> Any:  # noqa: ARG002
        return "caller-token"

    async def get_flow(self, flow_id: str, caller: Any) -> ResolvedFlow:  # noqa: ARG002
        return ResolvedFlow(flow_id=flow_id, graph=deepcopy(self._graph), session_id_default=flow_id)

    async def authorize(self, caller: Any, flow: ResolvedFlow, action: Any) -> None:  # noqa: ARG002
        self.authorized_actions.append(action)

    async def submit_background(self, parsed, flow, caller, *, stream_protocol) -> WorkflowJobResponse:  # noqa: ARG002
        return WorkflowJobResponse(job_id=str(uuid4()), flow_id=flow.flow_id, status=JobStatus.QUEUED)

    async def get_job_status(self, job_id, caller, session) -> WorkflowJobResponse:  # noqa: ARG002
        return WorkflowJobResponse(job_id=job_id, flow_id=_FLOW_ID, status=JobStatus.QUEUED)

    async def stop_job(self, job_id, caller) -> WorkflowStopResponse:  # noqa: ARG002
        return WorkflowStopResponse(job_id=job_id, message="stopped")


def _client(host: _FakeHost) -> TestClient:
    app = FastAPI()
    # developer_api_guard=False so the bare mount is not gated, matching serve.
    app.include_router(create_workflow_router(host, developer_api_guard=False))
    return TestClient(app)


def test_fake_host_satisfies_protocol():
    host = _FakeHost(_echo_graph())
    assert isinstance(host, WorkflowHost)


def test_sync_response_shape_validates_back_through_schema():
    host = _FakeHost(_echo_graph())
    client = _client(host)
    resp = client.post("/workflows", json={"flow_id": _FLOW_ID, "input_value": "hello", "mode": "sync"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["object"] == "response"
    assert body["flow_id"] == _FLOW_ID
    assert "status" in body
    assert "outputs" in body
    assert "has_errors" in body
    assert body["has_errors"] is False
    # The body validates back through the schema, pinning the wire contract.
    parsed = WorkflowExecutionResponse.model_validate(body)
    assert parsed.flow_id == _FLOW_ID
    assert "hello" in (parsed.output.text or "")


def test_authorize_receives_workflow_action_member():
    host = _FakeHost(_echo_graph())
    client = _client(host)
    resp = client.post("/workflows", json={"flow_id": _FLOW_ID, "input_value": "hello", "mode": "sync"})
    assert resp.status_code == 200, resp.text
    assert host.authorized_actions, "authorize was never called"
    action = host.authorized_actions[0]
    # A real enum member, not the raw "execute" string.
    assert isinstance(action, WorkflowAction)
    assert action is WorkflowAction.EXECUTE


def test_sse_frame_shape_and_terminal_frame():
    host = _FakeHost(_echo_graph())
    client = _client(host)
    resp = client.post(
        "/workflows",
        json={"flow_id": _FLOW_ID, "input_value": "hello", "mode": "stream", "stream_protocol": "agui"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    raw = resp.text
    # Split into frames on the blank-line delimiter.
    frames = [f for f in raw.split("\n\n") if f.strip()]
    assert frames, "no SSE frames emitted"
    for seq, frame in enumerate(frames):
        lines = frame.split("\n")
        assert lines[0] == f"id: {seq}", f"frame {seq} id line: {lines[0]!r}"
        assert lines[1].startswith("data: "), f"frame {seq} data line: {lines[1]!r}"
        # The data payload is valid JSON.
        json.loads(lines[1][len("data: ") :])
    # The agui adapter's terminal frame is RUN_FINISHED.
    assert "RUN_FINISHED" in raw


def test_background_unsupported_returns_422_and_no_job_endpoints():
    host = _FakeHost(_echo_graph(), supports_background=False)
    client = _client(host)
    resp = client.post("/workflows", json={"flow_id": _FLOW_ID, "input_value": "x", "mode": "background"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "LFX_SERVE_UNSUPPORTED_MODE"

    # The durable job endpoints are absent from the OpenAPI surface.
    paths = client.app.openapi()["paths"]
    assert set(paths) == {"/workflows"}
    assert "/workflows/stop" not in paths
    # GET on /workflows (job status) is not registered.
    assert "get" not in paths["/workflows"]


def test_background_supported_registers_job_endpoints():
    host = _FakeHost(_echo_graph(), supports_background=True)
    client = _client(host)
    paths = client.app.openapi()["paths"]
    assert "/workflows/stop" in paths
    # Both POST (run) and GET (status) live on /workflows when background is on.
    assert "post" in paths["/workflows"]
    assert "get" in paths["/workflows"]

    # And background mode now dispatches to the host instead of 422-ing.
    resp = client.post("/workflows", json={"flow_id": _FLOW_ID, "input_value": "x", "mode": "background"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["object"] == "job"
    assert body["flow_id"] == _FLOW_ID


def test_background_supported_but_job_routes_suppressed():
    """``supports_background=True`` with ``auto_register_job_routes=False`` keeps POST background.

    The langflow backend passes exactly this combination: background submit must
    still dispatch to ``host.submit_background`` (no 422), but the generic GET
    status + POST ``/stop`` routes must NOT be auto-registered because langflow
    mounts its own behaviorally-rich versions on the same prefix.
    """
    host = _FakeHost(_echo_graph(), supports_background=True)
    app = FastAPI()
    app.include_router(create_workflow_router(host, developer_api_guard=False, auto_register_job_routes=False))
    client = TestClient(app)

    paths = client.app.openapi()["paths"]
    # The generic job routes are absent — langflow mounts those itself.
    assert "/workflows/stop" not in paths
    assert "get" not in paths["/workflows"]
    # POST run path is present.
    assert "post" in paths["/workflows"]

    # Background submit still reaches the host instead of 422-ing.
    resp = client.post("/workflows", json={"flow_id": _FLOW_ID, "input_value": "x", "mode": "background"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["object"] == "job"
    assert body["flow_id"] == _FLOW_ID


def test_developer_api_guard_403_when_enabled_and_setting_off():
    """With the guard on and the lfx setting at its default (off), the router 403s."""
    host = _FakeHost(_echo_graph())
    app = FastAPI()
    app.include_router(create_workflow_router(host, developer_api_guard=True))
    client = TestClient(app)
    resp = client.post("/workflows", json={"flow_id": _FLOW_ID, "input_value": "x", "mode": "sync"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "DEVELOPER_API_DISABLED"


if __name__ == "__main__":
    pytest.main([__file__, "-x", "-q"])
