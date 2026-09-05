"""Slack ``ok:false`` bodies map onto lfx's sanitized error vocabulary.

Slack answers HTTP 200 for application-level failures, so without the bundle's
registered normalizer every one of these would surface as
``provider-unavailable`` and the frontend's code-keyed reconnect and
grant-scopes affordances would never fire.
"""

from __future__ import annotations

import pytest
from conftest import FakeResolver, SlackTransport, load_fixture
from lfx.integrations.errors import (
    ActionUnsupportedError,
    AuthExpiredError,
    IntegrationError,
    ProviderUnavailableError,
    RateLimitedError,
    ScopeMissingError,
    normalize_integration_error,
)
from lfx.integrations.models import (
    ConnectionRef,
    ConnectionResolutionRequest,
    CredentialLease,
)
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_slack._client import SLACK_API_BASE_URL, SlackClient, next_cursor
from slack_sdk.errors import SlackApiError

PRINCIPAL = ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True)


def _lease(resolver: FakeResolver) -> CredentialLease:
    request = ConnectionResolutionRequest(
        ref=ConnectionRef(provider="slack", name="workspace"),
        principal=PRINCIPAL,
        required_scopes=frozenset({"chat:write"}),
    )
    return CredentialLease(resolver, request)


def test_the_api_root_is_a_non_configurable_constant() -> None:
    assert SLACK_API_BASE_URL == "https://slack.com/api/"


@pytest.mark.parametrize(
    ("fixture", "expected", "code"),
    [
        ("error_invalid_auth", AuthExpiredError, "auth-expired"),
        ("error_token_expired", AuthExpiredError, "auth-expired"),
        ("error_missing_scope", ScopeMissingError, "scope-missing"),
        ("error_ratelimited", RateLimitedError, "rate-limited"),
        ("error_not_allowed_token_type", ActionUnsupportedError, "action-unsupported"),
        ("error_channel_not_found", ActionUnsupportedError, "action-unsupported"),
        ("error_internal_error", ProviderUnavailableError, "provider-unavailable"),
    ],
)
async def test_ok_false_bodies_map_to_typed_errors(
    transport: SlackTransport,
    fixture: str,
    expected: type[IntegrationError],
    code: str,
) -> None:
    # Enqueued twice: an auth rejection spends the one reactive re-resolve and
    # asks again, and a still-rejected token must surface the same typed error.
    transport.enqueue(load_fixture(fixture))
    transport.enqueue(load_fixture(fixture))
    client = SlackClient(_lease(FakeResolver()))

    with pytest.raises(expected) as raised:
        await client.call("chat_postMessage", channel="C0SLACKDEMO", text="hi")

    assert raised.value.code == code
    assert raised.value.provider == "slack"


async def test_missing_scope_reports_the_scopes_slack_asked_for(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("error_missing_scope"))
    client = SlackClient(_lease(FakeResolver()))

    with pytest.raises(ScopeMissingError) as raised:
        await client.call("conversations_members", channel="C0SLACKDEMO")

    assert raised.value.missing == frozenset({"users:read"})
    assert raised.value.details["missing"] == ["users:read"]


async def test_rate_limited_carries_retry_after(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("error_ratelimited"), status_code=429, headers={"Retry-After": "37"})
    client = SlackClient(_lease(FakeResolver()))

    with pytest.raises(RateLimitedError) as raised:
        await client.call("conversations_replies", channel="C0SLACKDEMO", ts="1700000000.000100")

    assert raised.value.retry_after == 37.0
    assert raised.value.retryable is True


async def test_http_429_without_a_slack_error_code_is_still_rate_limited(transport: SlackTransport) -> None:
    transport.enqueue({"ok": False}, status_code=429, headers={"retry-after": "5"})
    client = SlackClient(_lease(FakeResolver()))

    with pytest.raises(RateLimitedError) as raised:
        await client.call("reactions_add", channel="C0", timestamp="1.0", name="x")

    assert raised.value.retry_after == 5.0


async def test_error_messages_never_leak_the_token_or_a_handle(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("error_invalid_auth"))
    transport.enqueue(load_fixture("error_invalid_auth"))
    resolver = FakeResolver(tokens=["xoxp-secret-user-token"])  # pragma: allowlist secret
    client = SlackClient(_lease(resolver))

    with pytest.raises(AuthExpiredError) as raised:
        await client.call("search_messages", query="deploy")

    rendered = f"{raised.value.message} {raised.value.safe_message} {raised.value.hint} {raised.value.details}"
    assert "xoxp-secret-user-token" not in rendered
    assert "workspace" not in rendered


async def test_an_auth_rejection_re_resolves_exactly_once(transport: SlackTransport) -> None:
    """Slack tokens have no expiry unless the app rotates them, so a rejection is the signal."""
    transport.enqueue(load_fixture("error_invalid_auth"))
    transport.enqueue(load_fixture("chat_postmessage"))
    resolver = FakeResolver(tokens=["xoxp-stale", "xoxp-rotated"])  # pragma: allowlist secret
    client = SlackClient(_lease(resolver))

    body = await client.call("chat_postMessage", channel="C0SLACKDEMO", text="release is out")

    assert body["ts"] == "1700000200.000400"
    assert len(resolver.requests) == 2
    assert resolver.requests[1].rejected_token_digest is not None
    assert transport.calls[0].authorization == "Bearer xoxp-stale"
    assert transport.calls[1].authorization == "Bearer xoxp-rotated"


async def test_a_second_auth_rejection_stops_instead_of_looping(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("error_invalid_auth"))
    transport.enqueue(load_fixture("error_invalid_auth"))
    resolver = FakeResolver(tokens=["xoxp-stale", "xoxp-also-stale"])  # pragma: allowlist secret
    client = SlackClient(_lease(resolver))

    with pytest.raises(AuthExpiredError):
        await client.call("chat_postMessage", channel="C0SLACKDEMO", text="hi")

    assert len(transport.calls) == 2
    assert len(resolver.requests) == 2


async def test_none_valued_arguments_are_dropped(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("conversations_replies"))
    client = SlackClient(_lease(FakeResolver()))

    await client.call("conversations_replies", channel="C0SLACKDEMO", ts="1700000000.000100", cursor=None, limit=None)

    params = transport.last.params
    assert "cursor" not in params
    assert "limit" not in params
    assert params["channel"] == "C0SLACKDEMO"


def test_a_non_slack_exception_is_left_to_the_lfx_fallback() -> None:
    normalized = normalize_integration_error(TimeoutError("boom"), provider="slack")

    assert isinstance(normalized, ProviderUnavailableError)
    assert normalized.retryable is True


def test_next_cursor_treats_the_empty_string_as_the_last_page() -> None:
    assert next_cursor(load_fixture("search_messages")) == "dXNlcjpVMDYxTkZUVDI="
    assert next_cursor(load_fixture("conversations_members_last_page")) is None
    assert next_cursor({"ok": True}) is None


def test_the_normalizer_is_registered_for_slack() -> None:
    """A bare SlackApiError routed through lfx must come back typed."""
    body = {"ok": False, "error": "token_revoked"}
    response = type("Response", (), {"status_code": 200, "headers": {}, "data": body})
    error = SlackApiError("failed", response())

    normalized = normalize_integration_error(error, provider="slack")

    assert isinstance(normalized, AuthExpiredError)
