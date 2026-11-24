"""Router-level contract for serving-plane end-user session scoping.

No mocks of the router: a real ``WorkflowHostBase`` records the ``session_id`` the
router hands it, mounted on a bare ``FastAPI()`` with ``TestClient``, so these
assert the exact wire behavior both hosts inherit from ``execute_workflow``.

The settings service is STUBBED (``get_settings_service`` is monkeypatched to a
``SimpleNamespace``) for the per-flag matrix; one case
(``test_real_settings_env_binding_scopes_session``) drives a real env-built
``Settings`` object through the router to cover the operator-facing contract
end to end.
"""

from copy import deepcopy
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx.schema.workflow import JobStatus, WorkflowJobResponse
from lfx.workflow.host import ResolvedFlow, WorkflowHostBase
from lfx.workflow.router import create_workflow_router

_FLOW_ID = "67ccd2be-17f0-4190-81ff-3bb2cf6508e6"
HEADER = "X-End-User-Id"


def _echo_graph() -> Graph:
    chat_input = ChatInput(_id="chat_input")
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response)
    graph = Graph(chat_input, chat_output)
    graph.prepare()
    return graph


class _CaptureHost(WorkflowHostBase):
    """Background-capable host that records the session_id the router passes in."""

    supports_background = True

    def __init__(self, graph: Graph) -> None:
        self._graph = graph
        self.seen_session_id: str | None = "<unset>"
        self.seen_persist: bool | None = None
        self.seen_end_user_id: str | None = "<unset>"

    async def resolve_caller(self, request: Request) -> Any:  # noqa: ARG002
        return "caller"

    async def get_flow(self, flow_id: str, caller: Any) -> ResolvedFlow:  # noqa: ARG002
        return ResolvedFlow(flow_id=flow_id, graph=deepcopy(self._graph), session_id_default=flow_id)

    async def authorize(self, caller: Any, flow: ResolvedFlow, action: Any) -> None:  # noqa: ARG002
        return None

    async def submit_background(self, parsed, flow, caller, *, stream_protocol) -> WorkflowJobResponse:  # noqa: ARG002
        self.seen_session_id = parsed.session_id
        self.seen_persist = parsed.persist_messages
        self.seen_end_user_id = parsed.end_user_id
        return WorkflowJobResponse(job_id=str(uuid4()), flow_id=flow.flow_id, status=JobStatus.QUEUED)


def _settings(**overrides):
    base = {
        "serving_end_user_header": None,
        "serving_trust_proxy_headers": False,
        "serving_end_user_required": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def client_with_settings(monkeypatch):
    def _make(host: _CaptureHost, settings_ns):
        # The session scoping now reads settings inside the shared
        # ``resolve_serving_scope`` helper, which imports ``get_settings_service``
        # from ``lfx.services.deps`` at call time — so the stub is applied there
        # (not on the router module) for the router to observe it.
        from lfx.services import deps as deps_module

        monkeypatch.setattr(
            deps_module,
            "get_settings_service",
            lambda: SimpleNamespace(settings=settings_ns),
        )
        app = FastAPI()
        app.include_router(create_workflow_router(host, developer_api_guard=False, auto_register_job_routes=False))
        return TestClient(app)

    return _make


def _run(client, *, session_id=None, headers=None):
    body = {"flow_id": _FLOW_ID, "input_value": "hi", "mode": "background"}
    if session_id is not None:
        body["session_id"] = session_id
    return client.post("/workflows", json=body, headers=headers or {})


def test_identified_request_merges_end_user_into_session(client_with_settings):
    host = _CaptureHost(_echo_graph())
    client = client_with_settings(host, _settings(serving_end_user_header=HEADER, serving_trust_proxy_headers=True))
    resp = _run(client, session_id="chat-1", headers={HEADER: "alice"})
    assert resp.status_code == 200, resp.text
    assert host.seen_session_id == "alice::chat-1"
    # An identified run persists memory.
    assert host.seen_persist is True
    # The raw end-user id rides the parsed run so the build site can stamp the graph.
    assert host.seen_end_user_id == "alice"


def test_two_users_same_session_id_are_isolated(client_with_settings):
    settings = _settings(serving_end_user_header=HEADER, serving_trust_proxy_headers=True)

    host_a = _CaptureHost(_echo_graph())
    _run(client_with_settings(host_a, settings), session_id="shared", headers={HEADER: "alice"})

    host_b = _CaptureHost(_echo_graph())
    _run(client_with_settings(host_b, settings), session_id="shared", headers={HEADER: "bob"})

    assert host_a.seen_session_id != host_b.seen_session_id
    assert host_a.seen_session_id == "alice::shared"
    assert host_b.seen_session_id == "bob::shared"


def test_anonymous_request_gets_reserved_ephemeral_scope(client_with_settings):
    host = _CaptureHost(_echo_graph())
    client = client_with_settings(host, _settings(serving_end_user_header=HEADER, serving_trust_proxy_headers=True))
    resp = _run(client, session_id="chat-1")  # no header
    assert resp.status_code == 200, resp.text
    # The client-supplied session id is a read-scope key; an anonymous request
    # must not run under it (it could name an identified user's session). It is
    # moved into the reserved anon:: namespace instead.
    assert host.seen_session_id is not None
    assert host.seen_session_id.startswith("anon::")
    assert "chat-1" not in host.seen_session_id
    # An anonymous run is ephemeral: it must not persist memory.
    assert host.seen_persist is False
    # No identity => no end-user id stamped on the graph (falls back to the SID).
    assert host.seen_end_user_id is None


def test_anonymous_request_cannot_target_identified_scope(client_with_settings):
    # An anonymous caller posting an identified user's merged key must not land in
    # that user's namespace — this is the read-path half of the isolation contract.
    host = _CaptureHost(_echo_graph())
    client = client_with_settings(host, _settings(serving_end_user_header=HEADER, serving_trust_proxy_headers=True))
    resp = _run(client, session_id="alice::chat-1")  # no header
    assert resp.status_code == 200, resp.text
    assert host.seen_session_id != "alice::chat-1"
    assert "alice::chat-1" not in (host.seen_session_id or "")


def test_identified_echoed_session_id_is_not_rescoped(client_with_settings):
    # Turn 2 of the normal client contract: reuse the session_id from turn 1's
    # response. The merge must be idempotent or memory silently resets each turn.
    host = _CaptureHost(_echo_graph())
    client = client_with_settings(host, _settings(serving_end_user_header=HEADER, serving_trust_proxy_headers=True))
    resp = _run(client, session_id="alice::chat-1", headers={HEADER: "alice"})
    assert resp.status_code == 200, resp.text
    assert host.seen_session_id == "alice::chat-1"
    assert host.seen_persist is True


def test_feature_off_leaves_persist_default(client_with_settings):
    # With the feature off, parsed.persist_messages stays at its True default.
    host = _CaptureHost(_echo_graph())
    client = client_with_settings(host, _settings(serving_end_user_header=None))
    resp = _run(client, session_id="chat-1")
    assert resp.status_code == 200, resp.text
    assert host.seen_persist is True


def test_spoofed_header_ignored_when_trust_disabled(client_with_settings):
    # Feature on, but trust off: the client-supplied header must not scope memory.
    # The request runs as anonymous — reserved namespace, no persistence.
    host = _CaptureHost(_echo_graph())
    client = client_with_settings(host, _settings(serving_end_user_header=HEADER, serving_trust_proxy_headers=False))
    resp = _run(client, session_id="chat-1", headers={HEADER: "victim"})
    assert resp.status_code == 200, resp.text
    assert "victim" not in (host.seen_session_id or "")
    assert host.seen_session_id is not None
    assert host.seen_session_id.startswith("anon::")
    assert host.seen_persist is False


def test_feature_off_is_noop(client_with_settings):
    # Header unset ⇒ feature off: even a present header is ignored.
    host = _CaptureHost(_echo_graph())
    client = client_with_settings(host, _settings(serving_end_user_header=None))
    resp = _run(client, session_id="chat-1", headers={HEADER: "alice"})
    assert resp.status_code == 200, resp.text
    assert host.seen_session_id == "chat-1"


def test_required_rejects_anonymous_with_401(client_with_settings):
    host = _CaptureHost(_echo_graph())
    client = client_with_settings(
        host,
        _settings(serving_end_user_header=HEADER, serving_trust_proxy_headers=True, serving_end_user_required=True),
    )
    resp = _run(client, session_id="chat-1")  # no header
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"]["code"] == "END_USER_IDENTITY_REQUIRED"
    # The host never ran for a rejected request.
    assert host.seen_session_id == "<unset>"


def test_identified_without_session_falls_back_to_flow_id(client_with_settings):
    host = _CaptureHost(_echo_graph())
    client = client_with_settings(host, _settings(serving_end_user_header=HEADER, serving_trust_proxy_headers=True))
    resp = _run(client, headers={HEADER: "alice"})  # no session_id in body
    assert resp.status_code == 200, resp.text
    assert host.seen_session_id == f"alice::{_FLOW_ID}"


def test_real_settings_env_binding_scopes_session(client_with_settings, monkeypatch):
    """Operator contract end to end: the three env vars drive a real ``Settings``.

    The rest of this module stubs the settings namespace; this case builds the
    actual env-bound ``Settings`` object so a typo in a field name or the
    LANGFLOW_ prefix cannot silently disable the feature with every other test
    still green.
    """
    from lfx.services.settings.base import Settings

    monkeypatch.setenv("LANGFLOW_SERVING_END_USER_HEADER", HEADER)
    monkeypatch.setenv("LANGFLOW_SERVING_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("LANGFLOW_SERVING_END_USER_REQUIRED", "false")

    host = _CaptureHost(_echo_graph())
    client = client_with_settings(host, Settings())
    resp = _run(client, session_id="chat-1", headers={HEADER: "alice"})
    assert resp.status_code == 200, resp.text
    assert host.seen_session_id == "alice::chat-1"
    assert host.seen_persist is True


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
