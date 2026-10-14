"""INT-6: the typed integration branch of the client error policy.

Field names here are contract: INT-8's connection UI turns ``error_code`` into a
call to action, so a rename is a breaking change for the frontend.
"""

from __future__ import annotations

import asyncio
import json
import traceback
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.utils.execution_errors import (
    SAFE_INTEGRATION_ERROR_MESSAGE,
    SAFE_WORKFLOW_ERROR_MESSAGE,
    error_details_for_client,
    error_for_client,
    integration_http_error,
)
from langflow.services.database.models.message.model import MessageTable
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom import Component
from lfx.events.event_manager import create_default_event_manager
from lfx.exceptions.component import ComponentBuildError
from lfx.graph import Graph
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    ConnectionUnresolvedError,
    IncompatibleToolError,
    InvalidRequestError,
    RateLimitedError,
    ResourceNotFoundError,
    ScopeMissingError,
)
from lfx.io import ConnectionRefInput, MessageTextInput, Output
from lfx.schema.message import Message
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.integration_policy import IntegrationPolicyError, IntegrationPolicyPurpose, IntegrationPolicyService
from lfx.services.policy_bundle import PolicyBundleService, PolicyBundleSnapshot
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

HTTP_FORBIDDEN = 403
HTTP_UNAUTHORIZED = 401
HTTP_TOO_MANY_REQUESTS = 429


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ConnectionNotAuthorizedError(provider="google"), "connection-not-authorized"),
        (ConnectionUnresolvedError("google/work", provider="google"), "connection-unresolved"),
        (AuthExpiredError(provider="google"), "auth-expired"),
        (InvalidRequestError(provider="google"), "invalid-request"),
        (ResourceNotFoundError(provider="google"), "resource-not-found"),
        (ScopeMissingError(frozenset({"calendar.write"}), provider="google"), "scope-missing"),
        (RateLimitedError(provider="google", retry_after=12.0), "rate-limited"),
        (IncompatibleToolError(provider="google"), "incompatible-tool"),
        (IntegrationPolicyError("google", IntegrationPolicyPurpose.USE), "policy-blocked"),
    ],
)
def test_typed_fields_cross_every_error_policy(error, code) -> None:
    """Code, hint, provider and retry metadata are safe by construction.

    They are emitted to a delegated or anonymous caller too: a public visitor who
    is shown a bare sentence with no code has nothing to act on, and none of
    these fields name an account, a token, or an owner.
    """
    for expose_details in (True, False):
        details = error_details_for_client(error, expose_details=expose_details)

        assert details.code == code
        assert details.provider == "google"
        assert details.retryable is error.retryable
        assert details.stack_trace == ""
        body = details.as_client_body()
        assert body["error_code"] == code
        assert body["message"] == details.message


def test_sanitized_policy_drops_the_handle_but_keeps_the_code() -> None:
    """``ConnectionUnresolvedError`` names the handle; a delegated caller must not see it."""
    error = ConnectionUnresolvedError("google/work", provider="google")

    delegated = error_details_for_client(error, expose_details=False)
    owner = error_details_for_client(error, expose_details=True)

    assert "google/work" not in delegated.message
    assert delegated.message == SAFE_INTEGRATION_ERROR_MESSAGE
    assert "google/work" in owner.message
    assert delegated.code == owner.code == "connection-unresolved"


def test_the_owner_debug_policy_keeps_the_traceback_for_an_integration_failure() -> None:
    """A flow owner debugging their own run keeps what every other error class gives them."""
    error = ConnectionNotAuthorizedError(provider="google")
    trace = 'Traceback (most recent call last):\n  File "flow.py", line 1'

    owner = error_details_for_client(error, expose_details=True, stack_trace=trace)
    delegated = error_details_for_client(error, expose_details=False, stack_trace=trace)

    assert owner.stack_trace == trace
    assert delegated.stack_trace == ""


def test_sanitized_policy_drops_structured_details() -> None:
    error = ScopeMissingError(frozenset({"calendar.write"}), provider="google")

    assert error_details_for_client(error, expose_details=False).details == {}
    assert error_details_for_client(error, expose_details=True).details == {
        "missing": ["calendar.write"],
        "scopes_verified": True,
    }


def test_owner_error_body_carries_structured_details_and_delegated_does_not() -> None:
    """An owner's response names the missing scopes; a delegated caller gets only the code.

    The traceback is not part of this body: the build stream already sends it
    as ``stackTrace`` beside the typed body, and HTTP responses never carry one.
    """
    error = ScopeMissingError(frozenset({"calendar.write"}), provider="google")

    owner = error_for_client(error, expose_details=True)
    delegated = error_for_client(error, expose_details=False)

    assert isinstance(owner, HTTPException)
    assert isinstance(delegated, HTTPException)
    assert owner.detail["details"] == {"missing": ["calendar.write"], "scopes_verified": True}
    assert "details" not in delegated.detail
    assert "stack_trace" not in owner.detail


def test_retry_after_survives_for_a_rate_limited_provider() -> None:
    details = error_details_for_client(RateLimitedError(provider="google", retry_after=30.0), expose_details=False)

    assert details.retryable is True
    assert details.retry_after == 30.0
    assert details.as_client_body()["retry_after"] == 30.0


def test_error_for_client_returns_the_provider_status_not_a_generic_500() -> None:
    """An unauthorized connection is a 403, not a workflow crash."""
    for error, status in (
        (ConnectionNotAuthorizedError(provider="google"), HTTP_FORBIDDEN),
        (AuthExpiredError(provider="google"), HTTP_UNAUTHORIZED),
        (InvalidRequestError(provider="google"), 400),
        (ResourceNotFoundError(provider="google"), 404),
        (RateLimitedError(provider="google", retry_after=1.0), HTTP_TOO_MANY_REQUESTS),
        (IntegrationPolicyError("google", IntegrationPolicyPurpose.USE), HTTP_FORBIDDEN),
    ):
        client_error = error_for_client(error, expose_details=False)

        assert isinstance(client_error, HTTPException)
        assert client_error.status_code == status
        assert client_error.detail["error_code"] == error.code
        assert client_error.detail["message"] == SAFE_INTEGRATION_ERROR_MESSAGE


def test_non_integration_errors_are_unchanged() -> None:
    """The pre-existing policy for every other failure must not move."""
    failure = ValueError("component blew up with secret=hunter2")

    assert error_details_for_client(failure, expose_details=True).message == str(failure)
    assert error_details_for_client(failure, expose_details=False).message == SAFE_WORKFLOW_ERROR_MESSAGE
    assert error_details_for_client(failure, expose_details=False).code is None

    assert error_for_client(failure, expose_details=True) is failure
    sanitized = error_for_client(failure, expose_details=False)
    assert isinstance(sanitized, RuntimeError)
    assert str(sanitized) == SAFE_WORKFLOW_ERROR_MESSAGE

    http_failure = HTTPException(status_code=418, detail="teapot internals")
    sanitized_http = error_for_client(http_failure, expose_details=False)
    assert isinstance(sanitized_http, HTTPException)
    assert sanitized_http.status_code == 418
    assert sanitized_http.detail == SAFE_WORKFLOW_ERROR_MESSAGE


def test_integration_http_error_only_fires_for_integration_failures() -> None:
    """The terminal-handler guard must not divert ordinary component failures."""
    assert integration_http_error(ValueError("boom"), expose_details=False) is None
    assert integration_http_error(HTTPException(status_code=418, detail="teapot"), expose_details=False) is None

    typed = integration_http_error(ConnectionNotAuthorizedError(provider="google"), expose_details=False)

    assert isinstance(typed, HTTPException)
    assert typed.status_code == HTTP_FORBIDDEN
    assert typed.detail["error_code"] == "connection-not-authorized"
    assert typed.detail["hint"]


class ConnectionErrorProbe(Component):
    inputs = [MessageTextInput(name="input_value"), ConnectionRefInput(name="connection", provider="google")]
    outputs = [Output(name="result", display_name="Result", method="resolve")]

    async def resolve(self) -> Message:
        await self.resolve_connection("connection").get_token()
        return Message(text="resolved")


@pytest.mark.no_blockbuster
@pytest.mark.parametrize("expose_details", [False, True])
async def test_component_policy_denial_persists_in_session_history(monkeypatch, async_session, expose_details) -> None:
    """Read a committed error record back through a separate database session."""

    @asynccontextmanager
    async def database_session():
        yield async_session

    monkeypatch.setattr("langflow.memory.session_scope", database_session)
    monkeypatch.setattr("lfx.memory.has_langflow_db_backend", lambda: True)
    bundle = PolicyBundleService()
    bundle.publish(PolicyBundleSnapshot(revision=1, approved_integration_provider_ids={"slack"}))
    service = IntegrationPolicyService(policy_bundle_service=bundle)
    monkeypatch.setattr("lfx.services.deps.get_integration_policy_service", lambda: service)
    probe = ConnectionErrorProbe(connection="google/work")
    graph = Graph(start=probe, end=probe)
    graph.set_run_id(str(uuid4()))
    graph.session_id = "policy-denial-history"
    graph.expose_error_details = expose_details
    queue = asyncio.Queue()
    probe.set_event_manager(create_default_event_manager(queue))

    with pytest.raises(IntegrationPolicyError):
        await probe.build_results()

    async with AsyncSession(async_session.bind) as reader:
        rows = (await reader.exec(select(MessageTable).where(MessageTable.session_id == graph.session_id))).all()
        assert len(rows) == 1
        assert rows[0].category == "error"
        assert "policy-blocked" in rows[0].model_dump_json()
        assert "administrator" in rows[0].text
        assert "approved integration set" in rows[0].text

    payloads = []
    while not queue.empty():
        payloads.append(json.loads(queue.get_nowait()[1]))
    errors = [payload for payload in payloads if payload["event"] == "error"]
    assert errors
    rendered = json.dumps(errors)
    assert "policy-blocked" in rendered
    assert ("approved integration set" in rendered) is expose_details
    assert ("Traceback" in rendered) is expose_details


@pytest.mark.no_blockbuster
@pytest.mark.parametrize("policy_blocked", [False, True])
async def test_real_graph_connection_failure_keeps_typed_client_errors(monkeypatch, *, policy_blocked: bool) -> None:
    """Exercise the vertex and graph wrappers that real run/build handlers receive."""
    if policy_blocked:
        bundle = PolicyBundleService()
        bundle.publish(PolicyBundleSnapshot(revision=1, approved_integration_provider_ids={"slack"}))
        service = IntegrationPolicyService(policy_bundle_service=bundle)
        monkeypatch.setattr("lfx.services.deps.get_integration_policy_service", lambda: service)
    error_type = IntegrationPolicyError if policy_blocked else ConnectionNotAuthorizedError
    error_code = "policy-blocked" if policy_blocked else "connection-not-authorized"
    chat = ChatInput(_id="chat").set(input_value="hello", should_store_message=False)
    probe = ConnectionErrorProbe(_id="probe", connection="google/work").set(input_value=chat.message_response)
    output = ChatOutput(_id="output").set(input_value=probe.resolve, should_store_message=False)
    graph = Graph(start=chat, end=output, user_id=str(uuid4()))
    graph.execution_principal = ExecutionPrincipal(kind="anonymous_public", family="workflow_public_v2")

    with pytest.raises(ValueError, match="Error running graph") as caught:
        await graph.arun(inputs=[{"input_value": "hello"}], inputs_components=[[]], types=["chat"], outputs=["output"])

    graph_error = caught.value
    vertex_error = graph_error.__cause__
    assert isinstance(vertex_error, ComponentBuildError)
    assert isinstance(vertex_error.__cause__, error_type)
    trace = "".join(traceback.format_exception(type(graph_error), graph_error, graph_error.__traceback__))

    for expose_details in (True, False):
        # /build receives the vertex wrapper; /run receives the additional graph wrapper.
        for error in (vertex_error, graph_error):
            details = error_details_for_client(error, expose_details=expose_details, stack_trace=trace)
            assert details.code == error_code
            assert details.stack_trace == (trace if expose_details else "")
            assert details.message == (
                vertex_error.__cause__.safe_message if expose_details else SAFE_INTEGRATION_ERROR_MESSAGE
            )
            for mapped in (
                error_for_client(error, expose_details=expose_details),
                integration_http_error(error, expose_details=expose_details),
            ):
                assert isinstance(mapped, HTTPException)
                assert mapped.status_code == HTTP_FORBIDDEN
                assert mapped.detail == details.as_client_body()


@pytest.mark.parametrize("chain_attribute", ["__cause__", "__context__"])
@pytest.mark.parametrize(
    "error",
    [
        AuthExpiredError(provider="google"),
        RateLimitedError(provider="google", retry_after=12.0),
        ScopeMissingError(frozenset({"calendar.write"}), provider="google"),
        ConnectionUnresolvedError("google/work", provider="google"),
        IntegrationPolicyError("google", IntegrationPolicyPurpose.USE, policy_key="integrations.google.drive.delete"),
    ],
)
def test_wrapped_integration_errors_preserve_metadata_and_redaction(error, chain_attribute) -> None:
    wrapped = ValueError("wrapper with private component details")
    setattr(wrapped, chain_attribute, error)

    for expose_details in (True, False):
        assert error_details_for_client(wrapped, expose_details=expose_details) == error_details_for_client(
            error, expose_details=expose_details
        )
        expected = integration_http_error(error, expose_details=expose_details)
        for mapped in (
            integration_http_error(wrapped, expose_details=expose_details),
            error_for_client(wrapped, expose_details=expose_details),
        ):
            assert isinstance(mapped, HTTPException)
            assert mapped.status_code == expected.status_code
            assert mapped.detail == expected.detail


@pytest.mark.parametrize("suppression", ["from_none", "explicit_cause", "http_boundary"])
def test_explicit_error_translation_keeps_its_existing_policy(suppression) -> None:
    """Do not expose an integration failure a handler deliberately replaced."""
    original = AuthExpiredError(provider="google")
    replacement = HTTPException(status_code=404, detail="not found") if suppression == "http_boundary" else ValueError()
    replacement.__context__ = original
    if suppression == "from_none":
        replacement.__suppress_context__ = True
    elif suppression == "explicit_cause":
        replacement.__cause__ = RuntimeError("unrelated failure")
    else:
        replacement.__cause__ = original

    for expose_details in (True, False):
        assert error_details_for_client(replacement, expose_details=expose_details).code is None
        assert integration_http_error(replacement, expose_details=expose_details) is None
        mapped = error_for_client(replacement, expose_details=expose_details)
        if expose_details:
            assert mapped is replacement
        elif suppression == "http_boundary":
            assert isinstance(mapped, HTTPException)
            assert mapped.status_code == 404


def test_cyclic_exception_chain_is_not_an_integration_failure() -> None:
    error = ValueError("ordinary failure")
    cause = RuntimeError("another failure")
    error.__cause__ = cause
    cause.__cause__ = error

    assert error_details_for_client(error, expose_details=False).code is None
    assert integration_http_error(error, expose_details=False) is None
