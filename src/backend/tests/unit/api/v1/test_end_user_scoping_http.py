"""HTTP integration: the v1 ``/run`` endpoint scopes the session to the end-user.

Drives the real FastAPI stack (api-key auth -> ``simple_run_flow`` -> ``run_graph_internal``)
with the serving feature enabled, asserting the returned ``session_id`` reflects the
end-user scoping threaded through ``simple_run_flow``'s ``http_request``. This proves the
trusted header actually reaches the run over HTTP, complementing the lfx unit tests for
``resolve_serving_scope`` (which cover the decision in isolation).
"""

from uuid import uuid4

from fastapi import status

HEADER = "X-End-User-Id"


def _enable_serving(monkeypatch, *, required: bool = False) -> None:
    """Turn the serving end-user feature on for one test by mutating live settings.

    ``resolve_serving_scope`` reads these off ``get_settings_service().settings`` at call
    time, so patching that singleton's attributes (restored by monkeypatch) enables the
    feature for the request without rebuilding the app.
    """
    from lfx.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "serving_end_user_header", HEADER)
    monkeypatch.setattr(settings, "serving_trust_proxy_headers", True)
    monkeypatch.setattr(settings, "serving_end_user_required", required)


async def _run(client, flow_id, api_key, *, session_id=None, end_user=None):
    headers = {"x-api-key": api_key}
    if end_user is not None:
        headers[HEADER] = end_user
    payload: dict = {"input_value": "hi"}
    if session_id is not None:
        payload["session_id"] = session_id
    return await client.post(f"/api/v1/run/{flow_id}", headers=headers, json=payload)


async def test_identified_run_scopes_returned_session(client, simple_api_test, created_api_key, monkeypatch):
    _enable_serving(monkeypatch)
    resp = await _run(client, simple_api_test["id"], created_api_key.api_key, session_id="chat-1", end_user="alice")
    assert resp.status_code == status.HTTP_200_OK, resp.text
    # The run executed under the merged key, so the echoed session_id proves the header
    # reached run_graph_internal through simple_run_flow.
    assert resp.json()["session_id"] == "alice::chat-1"


async def test_two_end_users_same_session_are_isolated(client, simple_api_test, created_api_key, monkeypatch):
    _enable_serving(monkeypatch)
    flow_id = simple_api_test["id"]
    a = await _run(client, flow_id, created_api_key.api_key, session_id="shared", end_user="alice")
    b = await _run(client, flow_id, created_api_key.api_key, session_id="shared", end_user="bob")
    assert a.status_code == status.HTTP_200_OK, a.text
    assert b.status_code == status.HTTP_200_OK, b.text
    # Same client-supplied session id, different end users => distinct scopes.
    assert a.json()["session_id"] == "alice::shared"
    assert b.json()["session_id"] == "bob::shared"


async def test_anonymous_run_gets_reserved_scope(client, simple_api_test, created_api_key, monkeypatch):
    _enable_serving(monkeypatch)
    # Feature on but no identity header: the run is moved into the reserved anon::
    # namespace and must not land under the client-supplied session id.
    resp = await _run(client, simple_api_test["id"], created_api_key.api_key, session_id="chat-1")
    assert resp.status_code == status.HTTP_200_OK, resp.text
    session_id = resp.json()["session_id"]
    assert session_id.startswith("anon::")
    assert "chat-1" not in session_id


async def test_feature_off_leaves_session_unchanged(client, simple_api_test, created_api_key):
    # Default settings (no header configured): even a present header is ignored, so v1
    # /run is byte-for-byte its pre-feature self.
    resp = await _run(client, simple_api_test["id"], created_api_key.api_key, session_id="chat-1", end_user="alice")
    assert resp.status_code == status.HTTP_200_OK, resp.text
    assert resp.json()["session_id"] == "chat-1"


async def test_required_but_absent_is_rejected(client, simple_api_test, created_api_key, monkeypatch):
    _enable_serving(monkeypatch, required=True)
    resp = await _run(client, simple_api_test["id"], created_api_key.api_key, session_id="chat-1")  # no header
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED, resp.text
    assert resp.json()["detail"]["code"] == "END_USER_IDENTITY_REQUIRED"


async def _run_stream(client, flow_id, api_key, *, end_user=None):
    headers = {"x-api-key": api_key}
    if end_user is not None:
        headers[HEADER] = end_user
    return await client.post(f"/api/v1/run/{flow_id}?stream=true", headers=headers, json={"input_value": "hi"})


async def _responses(client, flow_id, api_key, *, stream=False, end_user=None):
    headers = {"x-api-key": api_key}
    if end_user is not None:
        headers[HEADER] = end_user
    body = {"model": flow_id, "input": "hi", "stream": stream}
    return await client.post("/api/v1/responses", headers=headers, json=body)


async def test_required_but_absent_rejected_on_streaming_run(client, simple_api_test, created_api_key, monkeypatch):
    # BUG-01: the stream branch returns a StreamingResponse (200 headers) before simple_run_flow
    # runs, so the 401 must come from a synchronous pre-check, not leak as an in-stream event.
    _enable_serving(monkeypatch, required=True)
    resp = await _run_stream(client, simple_api_test["id"], created_api_key.api_key)  # no header
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED, resp.text
    assert resp.json()["detail"]["code"] == "END_USER_IDENTITY_REQUIRED"


async def test_required_but_absent_rejected_on_responses(client, simple_api_test, created_api_key, monkeypatch):
    # BUG-01: create_response's blanket ``except Exception`` must not convert the 401 into an
    # OpenAIErrorResponse returned at the route's default 200.
    _enable_serving(monkeypatch, required=True)
    resp = await _responses(client, simple_api_test["id"], created_api_key.api_key)  # no header, sync
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED, resp.text
    assert resp.json()["detail"]["code"] == "END_USER_IDENTITY_REQUIRED"


async def test_required_but_absent_rejected_on_streaming_responses(
    client, simple_api_test, created_api_key, monkeypatch
):
    _enable_serving(monkeypatch, required=True)
    resp = await _responses(client, simple_api_test["id"], created_api_key.api_key, stream=True)  # no header
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED, resp.text
    assert resp.json()["detail"]["code"] == "END_USER_IDENTITY_REQUIRED"


async def test_streaming_run_with_identity_is_not_rejected(client, simple_api_test, created_api_key, monkeypatch):
    # Feature on + identity present: the pre-check is a no-op and the stream proceeds (BC).
    _enable_serving(monkeypatch, required=True)
    resp = await _run_stream(client, simple_api_test["id"], created_api_key.api_key, end_user="alice")
    assert resp.status_code == status.HTTP_200_OK, resp.text


async def test_identified_run_stamps_message_user_id_over_http(
    client, simple_api_test, created_api_key, active_user, monkeypatch
):
    """Full v1 chain: the header lands on message.user_id as the end user, not the SID.

    Proves header -> simple_run_flow -> graph.end_user_id -> _store_message -> the
    UUID-typed message.user_id column, and that the read predicate agrees (P2's
    write==read contract) over the real /run stack.
    """
    from langflow.memory import aget_messages

    _enable_serving(monkeypatch)
    uid = uuid4()  # a UUID-shaped end-user id is stamped directly
    resp = await _run(client, simple_api_test["id"], created_api_key.api_key, session_id="chat-1", end_user=str(uid))
    assert resp.status_code == status.HTTP_200_OK, resp.text
    scoped_session = resp.json()["session_id"]
    assert scoped_session == f"{uid}::chat-1"

    # Stored under the end user...
    assert len(await aget_messages(session_id=scoped_session, user_id=uid)) >= 1
    # ...and NOT under the service account (the api-key owner = SID).
    assert await aget_messages(session_id=scoped_session, user_id=active_user.id) == []
