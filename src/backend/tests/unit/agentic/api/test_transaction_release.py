"""Request-scoped DB transactions must end before long-running execution.

Issue #14445: the assistant endpoints (and the session-auth ``/run/session``
variant) do their auth/context reads on the request-scoped session, then await
a model or flow run that can take minutes. The transaction opened by those
reads stayed open for the whole run — on Postgres an ``idle in transaction``
connection that pins a pool slot and that a nonzero
``idle_in_transaction_session_timeout`` kills mid-run (the UI still gets a
result; the error surfaces at session cleanup).

The handlers now commit before starting the run. These tests pin that the
request session is no longer inside a transaction at the moment the execution
helper is invoked — and, for the SSE endpoint, while the stream body is being
produced (dependency teardown only runs after the stream finishes, so without
the fix the transaction spans the entire stream).

The API-key ``/run`` variant needs no test here: ``api_key_security`` scopes
its own short-lived session and never holds a request-scoped transaction.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from langflow.agentic.api.router import _AssistantContext
from sqlalchemy import inspect as sa_inspect

_ROUTER = "langflow.agentic.api.router"
_ENDPOINTS = "langflow.api.v1.endpoints"


@pytest.fixture
def _agentic_enabled(monkeypatch):
    from langflow.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "agentic_experience", True)


def _ctx_stub() -> _AssistantContext:
    return _AssistantContext(
        provider="OpenAI",
        model_name="gpt-4o",
        api_key_name="OPENAI_API_KEY",  # pragma: allowlist secret
        session_id="txn-release-test",
        global_vars={},
        max_retries=1,
    )


def _capturing_resolver(captured: dict):
    """Stand-in for ``_resolve_assistant_context`` that records the request session.

    The real resolver needs a configured provider; the endpoints under test
    only need a context object, so a canned one is returned. The session is
    recorded with its transaction still open (the auth dependency shares the
    same cached session and has already queried the user), which is asserted
    as a precondition so the final check cannot pass vacuously.
    """

    async def resolve(_request, _user_id, session):
        from lfx.services.model_provider_policy import current_model_provider_policy_context

        captured["session"] = session
        captured["provider_policy_preflight"] = current_model_provider_policy_context()
        assert session.in_transaction(), "precondition: the auth/context reads must have opened a transaction"
        return _ctx_stub()

    return resolve


@pytest.mark.usefixtures("_agentic_enabled")
async def test_assist_releases_transaction_before_model_run(client: AsyncClient, simple_api_test, logged_in_headers):
    captured: dict = {}

    async def fake_execute(**_kwargs):
        captured["in_transaction"] = captured["session"].in_transaction()
        return {"result": "ok"}

    with (
        patch(f"{_ROUTER}._resolve_assistant_context", side_effect=_capturing_resolver(captured)),
        patch(f"{_ROUTER}.execute_flow_with_validation", side_effect=fake_execute),
    ):
        response = await client.post(
            "api/v1/agentic/assist",
            json={"flow_id": simple_api_test["id"], "input_value": "build a flow"},
            headers=logged_in_headers,
        )

    assert response.status_code == 200, response.text
    assert captured["in_transaction"] is False, "the request transaction must be committed before the model run"
    assert captured["provider_policy_preflight"].attributes["provider_scope_required"] is True


@pytest.mark.usefixtures("_agentic_enabled")
async def test_assist_stream_releases_transaction_before_streaming(
    client: AsyncClient, simple_api_test, logged_in_headers
):
    captured: dict = {}

    def fake_stream(**_kwargs):
        async def gen():
            from lfx.services.model_provider_policy import current_model_provider_policy_context

            # Runs while the SSE body is streaming — after the handler returned
            # but before FastAPI tears down the session dependency.
            captured["in_transaction"] = captured["session"].in_transaction()
            captured["provider_policy_stream"] = current_model_provider_policy_context()
            yield 'data: {"event": "complete", "data": {"result": "ok"}}\n\n'

        return gen()

    with (
        patch(f"{_ROUTER}._resolve_assistant_context", side_effect=_capturing_resolver(captured)),
        patch(f"{_ROUTER}.execute_flow_with_validation_streaming", side_effect=fake_stream),
    ):
        response = await client.post(
            "api/v1/agentic/assist/stream",
            json={"flow_id": simple_api_test["id"], "input_value": "build a flow"},
            headers=logged_in_headers,
        )

    assert response.status_code == 200, response.text
    assert captured["in_transaction"] is False, "the request transaction must not span the assistant's SSE stream"
    assert captured["provider_policy_preflight"].attributes["provider_scope_required"] is True
    assert captured["provider_policy_stream"].attributes["provider_scope_required"] is True


@pytest.mark.usefixtures("_agentic_enabled")
async def test_execute_named_flow_releases_transaction_before_run(
    client: AsyncClient, simple_api_test, logged_in_headers
):
    captured: dict = {}

    async def fake_execute_flow_file(**_kwargs):
        captured["in_transaction"] = captured["session"].in_transaction()
        return {"result": "ok"}

    with (
        patch(f"{_ROUTER}._resolve_assistant_context", side_effect=_capturing_resolver(captured)),
        patch(f"{_ROUTER}.execute_flow_file", side_effect=fake_execute_flow_file),
    ):
        response = await client.post(
            "api/v1/agentic/execute/TestFlow",
            json={"flow_id": simple_api_test["id"], "input_value": "run it"},
            headers=logged_in_headers,
        )

    assert response.status_code == 200, response.text
    assert captured["in_transaction"] is False, "the request transaction must be committed before the named-flow run"
    assert captured["provider_policy_preflight"].attributes["provider_scope_required"] is True


@pytest.mark.parametrize(
    ("flow_id", "expected_status"),
    [("not-a-uuid", 422), ("00000000-0000-4000-8000-000000000001", 404)],
)
@pytest.mark.usefixtures("_agentic_enabled")
async def test_execute_named_flow_rejects_invalid_target_before_provider_discovery(
    client: AsyncClient,
    logged_in_headers,
    flow_id: str,
    expected_status: int,
):
    resolver = AsyncMock(side_effect=AssertionError("provider discovery reached before target validation"))
    with patch(f"{_ROUTER}._resolve_assistant_context", resolver):
        response = await client.post(
            "api/v1/agentic/execute/TestFlow",
            json={"flow_id": flow_id, "input_value": "run it"},
            headers=logged_in_headers,
        )

    assert response.status_code == expected_status, response.text
    resolver.assert_not_awaited()


@pytest.mark.usefixtures("_agentic_enabled")
async def test_run_session_releases_auth_transaction_before_flow_run(
    client: AsyncClient, simple_api_test, logged_in_headers
):
    """``/run/session`` opens its session via the auth chain (``CurrentActiveUser``).

    The authenticated ORM user is loaded by that session, so inspecting the
    user's owning session at execution time observes the exact transaction the
    auth reads opened.
    """
    captured: dict = {}

    async def fake_run_flow_internal(**kwargs):
        state = sa_inspect(kwargs["api_key_user"])
        session = state.session
        assert session is not None, "precondition: the auth-loaded user must still be attached to the request session"
        captured["in_transaction"] = session.in_transaction()
        return {"status": "ok"}

    with patch(f"{_ENDPOINTS}._run_flow_internal", side_effect=fake_run_flow_internal):
        response = await client.post(f"api/v1/run/session/{simple_api_test['id']}", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    assert captured["in_transaction"] is False, "the auth transaction must be committed before the flow run"


async def test_run_advanced_releases_transaction_before_graph_execution(
    client: AsyncClient, simple_api_test, created_api_key, monkeypatch
):
    """``/run/advanced`` must end its flow re-query transaction before ``run_graph_internal``.

    The handler passes neither the session nor a session-loaded ORM object to
    ``run_graph_internal``, so the request session is captured at its source:
    the ``injectable_session_scope`` dependency resolves ``session_scope``
    through the ``lfx.services.deps`` module namespace at call time.
    """
    import lfx.services.deps as lfx_deps

    request_sessions: list = []
    real_scope = lfx_deps.session_scope

    @asynccontextmanager
    async def capturing_scope():
        async with real_scope() as scoped_session:
            request_sessions.append(scoped_session)
            yield scoped_session

    monkeypatch.setattr(lfx_deps, "session_scope", capturing_scope)

    captured: dict = {}

    async def fake_run_graph_internal(**kwargs):
        assert request_sessions, "precondition: the request must have resolved the DbSession dependency"
        captured["in_transaction"] = [s.in_transaction() for s in request_sessions]
        return [], kwargs.get("session_id") or "txn-release-test"

    with patch(f"{_ENDPOINTS}.run_graph_internal", side_effect=fake_run_graph_internal):
        response = await client.post(
            f"api/v1/run/advanced/{simple_api_test['id']}",
            json={},
            headers={"x-api-key": created_api_key.api_key},
        )

    assert response.status_code == 200, response.text
    assert captured["in_transaction"] == [False] * len(captured["in_transaction"]), (
        "the flow re-query transaction must be committed before graph execution"
    )


async def test_webhook_events_releases_auth_transaction_before_streaming(
    client: AsyncClient, simple_api_test, logged_in_headers, monkeypatch
):
    """``/webhook-events`` must not hold the auth transaction across the EventSource stream.

    The stream is indefinite and dependency teardown only runs when it ends,
    so without a release every open tab pins a pooled connection in an idle
    transaction.

    The SSE auth chain loads the ORM user on the request session; wrapping
    ``ensure_flow_permission`` captures it. The transaction check runs inside a
    stubbed ``webhook_event_manager.subscribe`` — the first await of the stream
    body, i.e. after the handler returned but before dependency teardown. The
    stub also flips ``is_disconnected`` so the otherwise-endless stream ends
    immediately (httpx's ASGITransport cannot early-close a live stream).
    """
    import asyncio

    import langflow.api.v1.endpoints as endpoints_module
    from starlette.requests import Request

    captured: dict = {}
    real_ensure = endpoints_module.ensure_flow_permission

    async def capturing_ensure(user, *args, **kwargs):
        captured["user"] = user
        return await real_ensure(user, *args, **kwargs)

    async def fake_subscribe(_flow_id):
        state = sa_inspect(captured["user"])
        session = state.session
        assert session is not None, "precondition: the SSE auth user must still be attached to the request session"
        captured["in_transaction"] = session.in_transaction()
        return asyncio.Queue()

    async def fake_unsubscribe(_flow_id, _queue):
        return None

    async def fake_is_disconnected(_self):
        # False during the handler; True once the stream body has started and
        # the capture ran, so the event loop exits after the connected event.
        return "in_transaction" in captured

    monkeypatch.setattr(endpoints_module.webhook_event_manager, "subscribe", fake_subscribe)
    monkeypatch.setattr(endpoints_module.webhook_event_manager, "unsubscribe", fake_unsubscribe)
    monkeypatch.setattr(Request, "is_disconnected", fake_is_disconnected)

    # The SSE route authenticates via cookie (or x-api-key), not the
    # Authorization header — reuse the logged-in token as the cookie.
    token = logged_in_headers["Authorization"].removeprefix("Bearer ")

    with patch(f"{_ENDPOINTS}.ensure_flow_permission", side_effect=capturing_ensure):
        response = await client.get(
            f"api/v1/webhook-events/{simple_api_test['id']}",
            cookies={"access_token_lf": token},
        )

    assert response.status_code == 200, response.text
    assert "event: connected" in response.text
    assert captured["in_transaction"] is False, "the auth transaction must not span the webhook EventSource stream"
