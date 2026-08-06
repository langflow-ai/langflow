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

from unittest.mock import patch
from uuid import uuid4

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
        captured["session"] = session
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


@pytest.mark.usefixtures("_agentic_enabled")
async def test_assist_stream_releases_transaction_before_streaming(
    client: AsyncClient, simple_api_test, logged_in_headers
):
    captured: dict = {}

    def fake_stream(**_kwargs):
        async def gen():
            # Runs while the SSE body is streaming — after the handler returned
            # but before FastAPI tears down the session dependency.
            captured["in_transaction"] = captured["session"].in_transaction()
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


@pytest.mark.usefixtures("_agentic_enabled")
async def test_execute_named_flow_releases_transaction_before_run(client: AsyncClient, logged_in_headers):
    captured: dict = {}

    async def fake_execute_flow_file(**_kwargs):
        captured["in_transaction"] = captured["session"].in_transaction()
        return {"result": "ok"}

    with (
        patch(f"{_ROUTER}._resolve_assistant_context", side_effect=_capturing_resolver(captured)),
        patch(f"{_ROUTER}.execute_flow_file", side_effect=fake_execute_flow_file),
    ):
        # ``/execute/{flow_name}`` does not validate flow_id; any UUID works.
        response = await client.post(
            "api/v1/agentic/execute/TestFlow",
            json={"flow_id": str(uuid4()), "input_value": "run it"},
            headers=logged_in_headers,
        )

    assert response.status_code == 200, response.text
    assert captured["in_transaction"] is False, "the request transaction must be committed before the named-flow run"


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
