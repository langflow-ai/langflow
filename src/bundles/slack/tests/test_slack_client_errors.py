"""Slack ``ok:false`` bodies map onto lfx's sanitized error vocabulary.

Slack answers HTTP 200 for application-level failures, so without the bundle's
registered normalizer every one of these would surface as
``provider-unavailable`` and the frontend's code-keyed reconnect and
grant-scopes affordances would never fire.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from conftest import FakeResolver, SlackTransport, load_fixture
from lfx.integrations.errors import (
    ActionUnsupportedError,
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    IntegrationError,
    InvalidRequestError,
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
from lfx_slack import _client as slack_client
from lfx_slack._client import SLACK_API_BASE_URL, SlackClient, next_cursor, normalize_slack_error
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
        ("error_channel_not_found", InvalidRequestError, "invalid-request"),
        ("error_not_in_channel", InvalidRequestError, "invalid-request"),
        ("error_invalid_name", InvalidRequestError, "invalid-request"),
        ("error_invalid_blocks_format", InvalidRequestError, "invalid-request"),
        ("error_no_text", InvalidRequestError, "invalid-request"),
        ("error_restricted_action", ConnectionNotAuthorizedError, "connection-not-authorized"),
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


def _slack_api_error(code: str | None, *, status: int = 200) -> SlackApiError:
    body = {"ok": False} if code is None else {"ok": False, "error": code}
    response = type("Response", (), {"status_code": status, "headers": {}, "data": body})
    return SlackApiError("failed", response())


@pytest.mark.parametrize(
    ("fixture", "method", "kwargs"),
    [
        ("error_invalid_name", "reactions_add", {"channel": "C0SLACKDEMO", "timestamp": "1.0", "name": "nope"}),
        (
            "error_invalid_blocks_format",
            "chat_postMessage",
            {"channel": "C0SLACKDEMO", "text": "fallback", "blocks": "not-json"},
        ),
        ("error_no_text", "chat_postMessage", {"channel": "C0SLACKDEMO", "text": ""}),
    ],
)
@pytest.mark.filterwarnings("ignore:The top-level `text` argument is missing:UserWarning")
async def test_caller_fault_rejections_are_not_retryable(
    transport: SlackTransport,
    fixture: str,
    method: str,
    kwargs: dict,
) -> None:
    """LE-2470: these reached users as "temporarily unavailable, retry later"."""
    transport.enqueue(load_fixture(fixture))
    client = SlackClient(_lease(FakeResolver()))

    with pytest.raises(InvalidRequestError) as raised:
        await client.call(method, **kwargs)

    error = raised.value
    assert error.code == "invalid-request"
    assert error.retryable is False
    assert error.http_status == 400
    assert "retry" not in (error.hint or "").lower()
    assert "temporarily unavailable" not in error.message
    assert len(transport.calls) == 1


@pytest.mark.parametrize("code", ["channel_not_found", "not_in_channel"])
def test_membership_rejections_name_the_channel_remedy(code: str) -> None:
    error = normalize_slack_error(_slack_api_error(code))

    assert isinstance(error, InvalidRequestError)
    assert error.retryable is False
    hint = (error.hint or "").lower()
    assert "invite the app" in hint
    assert "does not support" not in error.message
    if code == "channel_not_found":
        assert "channel id" in hint


@pytest.mark.parametrize("code", ["restricted_action", "team_access_not_granted", "no_permission", "access_denied"])
def test_workspace_denials_are_provider_authorization_denials(code: str) -> None:
    error = normalize_slack_error(_slack_api_error(code))

    assert isinstance(error, ConnectionNotAuthorizedError)
    assert error.details == {"reason": "provider"}
    assert error.retryable is False


def test_an_unrecognized_slack_code_stays_provider_unavailable() -> None:
    error = normalize_slack_error(_slack_api_error("a_code_slack_adds_later"))

    assert isinstance(error, ProviderUnavailableError)
    assert error.retryable is True


@pytest.mark.parametrize(
    ("code", "status", "expected_status"),
    [
        ("invalid_auth", 200, 401),
        ("ratelimited", 200, 429),
        ("no_text", 200, 400),
        ("msg_too_long", 200, 400),
        ("channel_not_found", 200, 400),
        ("not_allowed_token_type", 200, None),
        ("internal_error", 200, None),
        ("internal_error", 503, 503),
        (None, 502, 502),
    ],
)
def test_slack_http_200_never_becomes_the_error_status(
    code: str | None, status: int, expected_status: int | None
) -> None:
    """A terminal run handler answers with ``http_status``; a 200 would report a failed run as a success."""
    error = normalize_slack_error(_slack_api_error(code, status=status))

    assert error is not None
    assert error.http_status == expected_status


@pytest.mark.parametrize("code", ["invalid_auth", "missing_scope", "ratelimited", "no_text", "restricted_action"])
@pytest.mark.parametrize("status", [500, 502, 503])
def test_a_slack_5xx_is_provider_unavailable_whatever_the_body_says(code: str, status: int) -> None:
    """A server-side failure is not evidence about the token, the scopes, or the inputs."""
    error = normalize_slack_error(_slack_api_error(code, status=status))

    assert isinstance(error, ProviderUnavailableError)
    assert error.http_status == status
    assert error.retryable is True


async def test_a_5xx_auth_code_does_not_spend_the_reactive_re_resolve(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("error_invalid_auth"), status_code=503)
    transport.enqueue(load_fixture("chat_postmessage"))
    resolver = FakeResolver(tokens=["xoxp-still-valid", "xoxp-unneeded"])  # pragma: allowlist secret
    client = SlackClient(_lease(resolver))

    with pytest.raises(ProviderUnavailableError) as raised:
        await client.call("chat_postMessage", channel="C0SLACKDEMO", text="hi")

    assert raised.value.http_status == 503
    assert len(transport.calls) == 1
    assert len(resolver.requests) == 1


def test_the_error_code_families_do_not_overlap() -> None:
    """The normalizer checks families in order, so an overlap would silently shadow a code."""
    families = {
        "auth": slack_client._AUTH_ERROR_CODES,
        "rate": slack_client._RATE_LIMIT_ERROR_CODES,
        "channel": frozenset({slack_client._CHANNEL_NOT_FOUND, slack_client._NOT_IN_CHANNEL}),
        "invalid": slack_client._INVALID_REQUEST_ERROR_CODES,
        "denied": slack_client._PROVIDER_DENIED_ERROR_CODES,
        "unsupported": slack_client._UNSUPPORTED_ERROR_CODES,
    }
    names = list(families)
    for index, left in enumerate(names):
        assert "missing_scope" not in families[left]
        for right in names[index + 1 :]:
            assert not families[left] & families[right], f"{left} and {right} share codes"


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


async def test_a_multi_request_action_uses_a_proactively_refreshed_token(
    monkeypatch: pytest.MonkeyPatch,
    transport: SlackTransport,
) -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    expires_at = now + timedelta(hours=1)
    resolver = FakeResolver(tokens=["xoxp-first", "xoxp-refreshed"])  # pragma: allowlist secret
    original_resolve = resolver.resolve

    async def resolve(request):
        credential = await original_resolve(request)
        return replace(credential, expires_at=expires_at) if len(resolver.requests) == 1 else credential

    monkeypatch.setattr(resolver, "resolve", resolve)
    lease = CredentialLease(
        resolver,
        ConnectionResolutionRequest(ref=ConnectionRef(provider="slack", name="workspace"), principal=PRINCIPAL),
        now=lambda: now,
    )
    client = SlackClient(lease)
    transport.enqueue(load_fixture("users_info"))
    transport.enqueue(load_fixture("users_info"))

    await client.call("users_info", user="U001")
    now = expires_at
    await client.call("users_info", user="U002")

    assert len(resolver.requests) == 2
    assert [call.authorization for call in transport.calls] == ["Bearer xoxp-first", "Bearer xoxp-refreshed"]


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
