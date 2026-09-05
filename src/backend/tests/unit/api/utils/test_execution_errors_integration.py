"""INT-6: the typed integration branch of the client error policy.

Field names here are contract: INT-8's connection UI turns ``error_code`` into a
call to action, so a rename is a breaking change for the frontend.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from langflow.api.utils.execution_errors import (
    SAFE_INTEGRATION_ERROR_MESSAGE,
    SAFE_WORKFLOW_ERROR_MESSAGE,
    error_details_for_client,
    error_for_client,
    integration_http_error,
)
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    ConnectionUnresolvedError,
    RateLimitedError,
    ScopeMissingError,
)

HTTP_FORBIDDEN = 403
HTTP_UNAUTHORIZED = 401
HTTP_TOO_MANY_REQUESTS = 429


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ConnectionNotAuthorizedError(provider="google"), "connection-not-authorized"),
        (ConnectionUnresolvedError("google/work", provider="google"), "connection-unresolved"),
        (AuthExpiredError(provider="google"), "auth-expired"),
        (ScopeMissingError(frozenset({"calendar.write"}), provider="google"), "scope-missing"),
        (RateLimitedError(provider="google", retry_after=12.0), "rate-limited"),
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


def test_sanitized_policy_drops_structured_details() -> None:
    error = ScopeMissingError(frozenset({"calendar.write"}), provider="google")

    assert error_details_for_client(error, expose_details=False).details == {}
    assert error_details_for_client(error, expose_details=True).details == {"missing": ["calendar.write"]}


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
        (RateLimitedError(provider="google", retry_after=1.0), HTTP_TOO_MANY_REQUESTS),
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
