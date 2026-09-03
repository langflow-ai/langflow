from __future__ import annotations

import builtins

import httpx
import pytest
from lfx.integrations import (
    INTEGRATION_ERROR_CODES,
    AuthExpiredError,
    IntegrationError,
    ProviderUnavailableError,
    RateLimitedError,
    normalize_integration_error,
    register_error_normalizer,
)


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://provider.example/private?token=secret")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("provider rejected user@example.com", request=request, response=response)


def test_integration_error_codes_are_stable() -> None:
    assert {
        "connection-unresolved",
        "connection-not-authorized",
        "auth-expired",
        "scope-missing",
        "rate-limited",
        "provider-unavailable",
        "action-unsupported",
    } == INTEGRATION_ERROR_CODES


@pytest.mark.parametrize(
    ("status", "error_type"),
    [(401, AuthExpiredError), (429, RateLimitedError), (500, ProviderUnavailableError)],
)
def test_normalize_integration_error_maps_http_status(status: int, error_type: type[IntegrationError]) -> None:
    assert isinstance(normalize_integration_error(_http_error(status), provider="google"), error_type)


def test_normalize_integration_error_unwraps_exception_groups() -> None:
    group_type = getattr(builtins, "ExceptionGroup", None)
    if group_type is None:
        group_type = pytest.importorskip("exceptiongroup").ExceptionGroup
    grouped = group_type("provider call", [RuntimeError("outer"), _http_error(401)])

    assert isinstance(normalize_integration_error(grouped, provider="google"), AuthExpiredError)


def test_integration_error_sanitizes_urls_and_email() -> None:
    error = IntegrationError(
        "failed for user@example.com at https://example.com/path?token=secret",
        details={"upstream": "https://example.com/private?token=secret"},
    )

    rendered = str(error)
    assert "user@example.com" not in rendered
    assert "token=secret" not in rendered
    assert "token=secret" not in error.details["upstream"]


def test_bundle_can_register_provider_error_normalizer() -> None:
    register_error_normalizer("test-provider", lambda _exc: AuthExpiredError(provider="test-provider"))

    assert isinstance(normalize_integration_error(RuntimeError("unsafe"), provider="test-provider"), AuthExpiredError)
