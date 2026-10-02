"""Identity mismatches fail closed before the first Slack request.

Slack user and bot tokens share scope names, so ``granted_scopes`` cannot tell
them apart, and ``chat.postMessage`` accepts both token types, so Slack's own
``not_allowed_token_type`` is no backstop either. Without this guard a message
could post under the wrong identity with no error at all.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from conftest import FakeResolver, SlackTransport, build_component, load_fixture
from lfx.integrations.errors import ConnectionNotAuthorizedError
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.connection.env_resolver import EnvConnectionResolver
from lfx_slack import SlackPostAsAppComponent, SlackSearchComponent, SlackSendAsUserComponent
from lfx_slack._base import SlackIdentityMismatchError, SlackIdentityUnverifiedError, token_identity

_TOKEN_FOR = {
    "bot": "xoxb-bot-token",  # pragma: allowlist secret
    "user_delegated": "xoxp-user-token",  # pragma: allowlist secret
}


def _resolver(
    monkeypatch: pytest.MonkeyPatch,
    identity: str | None,
    *,
    tokens: list[str] | None = None,
) -> FakeResolver:
    fake = FakeResolver(identity=identity, tokens=tokens or [_TOKEN_FOR[identity]])
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: fake)
    return fake


async def test_a_bot_action_refuses_a_user_connection(
    monkeypatch: pytest.MonkeyPatch,
    transport: SlackTransport,
) -> None:
    _resolver(monkeypatch, "user_delegated")
    component = build_component(SlackPostAsAppComponent, channel="C0SLACKDEMO", text="hi")

    with pytest.raises(SlackIdentityMismatchError) as raised:
        await component.build_message()

    assert raised.value.code == "connection-not-authorized"
    assert raised.value.expected == "bot"
    assert raised.value.actual == "user_delegated"
    assert "requires a bot token" in raised.value.message
    assert transport.calls == [], "the guard must fire before any HTTP call"


async def test_a_user_action_refuses_a_bot_connection(
    monkeypatch: pytest.MonkeyPatch,
    transport: SlackTransport,
) -> None:
    _resolver(monkeypatch, "bot")
    component = build_component(SlackSearchComponent, query="deploy")

    with pytest.raises(SlackIdentityMismatchError) as raised:
        await component.build_matches()

    assert raised.value.expected == "user_delegated"
    assert transport.calls == []


async def test_the_mismatch_is_a_connection_authorization_denial(
    monkeypatch: pytest.MonkeyPatch,
    transport: SlackTransport,
) -> None:
    """Hosts and the frontend key off the error code, not the class."""
    _resolver(monkeypatch, "bot")
    component = build_component(SlackSearchComponent, query="deploy")

    with pytest.raises(ConnectionNotAuthorizedError) as raised:
        await component.build_matches()

    assert raised.value.http_status == 403
    assert raised.value.provider == "slack"
    assert transport.calls == []


@pytest.mark.parametrize(
    ("token", "identity"),
    [
        ("xoxb-1-bot", "bot"),  # pragma: allowlist secret
        ("xoxp-1-user", "user_delegated"),  # pragma: allowlist secret
        ("xoxe.xoxb-1-rotating-bot", "bot"),  # pragma: allowlist secret
        ("xoxe.xoxp-1-rotating-user", "user_delegated"),  # pragma: allowlist secret
        ("xoxe-1-refresh-token", None),  # pragma: allowlist secret
        ("xapp-1-app-level-token", None),
        ("opaque-token", None),
        ("", None),
    ],
)
def test_the_token_prefix_proves_the_identity(token: str, identity: str | None) -> None:
    assert token_identity(token) == identity


@pytest.mark.parametrize(
    ("component_class", "token"),
    [
        (SlackPostAsAppComponent, "xoxb-headless-bot"),  # pragma: allowlist secret
        (SlackPostAsAppComponent, "xoxe.xoxb-headless-bot"),  # pragma: allowlist secret
        (SlackSendAsUserComponent, "xoxp-headless-user"),  # pragma: allowlist secret
    ],
)
async def test_a_headless_token_whose_prefix_matches_the_action_runs(
    monkeypatch: pytest.MonkeyPatch,
    transport: SlackTransport,
    component_class: type,
    token: str,
) -> None:
    """LF_CONNECTION__SLACK__* has no place to declare an identity; the prefix proves it."""
    _resolver(monkeypatch, None, tokens=[token])
    transport.enqueue(load_fixture("chat_postmessage"))
    component = build_component(component_class, channel="C0SLACKDEMO", text="hi")

    message = await component.build_message()

    assert message.data["ts"] == "1700000200.000400"
    assert transport.last.authorization == f"Bearer {token}"


@pytest.mark.parametrize(
    ("component_class", "token", "actual"),
    [
        (SlackSendAsUserComponent, "xoxb-headless-bot", "bot"),  # pragma: allowlist secret
        (SlackPostAsAppComponent, "xoxp-headless-user", "user_delegated"),  # pragma: allowlist secret
    ],
)
async def test_a_headless_token_of_the_other_identity_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    transport: SlackTransport,
    component_class: type,
    token: str,
    actual: str,
) -> None:
    """LE-2470: without a recorded identity, both of these used to post under the wrong author."""
    _resolver(monkeypatch, None, tokens=[token])
    component = build_component(component_class, channel="C0SLACKDEMO", text="hi")

    with pytest.raises(SlackIdentityMismatchError) as raised:
        await component.build_message()

    assert raised.value.code == "connection-not-authorized"
    assert raised.value.actual == actual
    assert transport.calls == [], "the guard must fire before any HTTP call"


async def test_a_token_that_proves_no_identity_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    transport: SlackTransport,
) -> None:
    _resolver(monkeypatch, None, tokens=["opaque-headless-token"])  # pragma: allowlist secret
    component = build_component(SlackPostAsAppComponent, channel="C0SLACKDEMO", text="hi")

    with pytest.raises(SlackIdentityUnverifiedError) as raised:
        await component.build_message()

    error = raised.value
    assert isinstance(error, ConnectionNotAuthorizedError)
    assert error.code == "connection-not-authorized"
    assert error.http_status == 403
    assert error.retryable is False
    assert "requires a bot token" in error.message
    assert "xoxb-" in (error.hint or "")  # pragma: allowlist secret
    rendered = f"{error.message} {error.safe_message} {error.hint} {error.details}"
    assert "opaque-headless-token" not in rendered
    assert transport.calls == []


async def test_a_token_that_contradicts_the_recorded_identity_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    transport: SlackTransport,
) -> None:
    """The token is what Slack acts on, so it must agree with the connection row too."""
    _resolver(monkeypatch, "bot", tokens=["xoxp-user-token-on-a-bot-row"])  # pragma: allowlist secret
    component = build_component(SlackPostAsAppComponent, channel="C0SLACKDEMO", text="hi")

    with pytest.raises(SlackIdentityMismatchError) as raised:
        await component.build_message()

    assert raised.value.expected == "bot"
    assert raised.value.actual == "user_delegated"
    assert transport.calls == []


async def test_a_recorded_identity_still_vouches_for_a_token_without_a_prefix(
    monkeypatch: pytest.MonkeyPatch,
    transport: SlackTransport,
) -> None:
    """A host that records the identity keeps working with opaque test tokens."""
    _resolver(monkeypatch, "bot", tokens=["opaque-host-token"])  # pragma: allowlist secret
    transport.enqueue(load_fixture("chat_postmessage"))
    component = build_component(SlackPostAsAppComponent, channel="C0SLACKDEMO", text="hi")

    await component.build_message()

    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    ("component_class", "token", "actual"),
    [
        (SlackSendAsUserComponent, "xoxb-env-bot", "bot"),  # pragma: allowlist secret
        (SlackPostAsAppComponent, "xoxp-env-user", "user_delegated"),  # pragma: allowlist secret
    ],
)
async def test_the_env_resolver_path_refuses_the_other_identity(
    monkeypatch: pytest.MonkeyPatch,
    transport: SlackTransport,
    component_class: type,
    token: str,
    actual: str,
) -> None:
    """The LE-2470 repro, end to end through ``EnvConnectionResolver``."""
    monkeypatch.setenv(
        "LF_CONNECTION__SLACK__QA",
        json.dumps({"access_token": token, "token_type": "Bearer", "scopes": ["chat:write"]}),
    )
    resolver = EnvConnectionResolver()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    component = component_class(connection="slack/qa", channel="C0SLACKDEMO", text="hi")
    component.set_vertex(
        SimpleNamespace(
            graph=SimpleNamespace(
                execution_principal=ExecutionPrincipal(kind="headless_operator"), flow_id=None, run_id=None
            )
        )
    )

    with pytest.raises(SlackIdentityMismatchError) as raised:
        await component.build_message()

    assert raised.value.actual == actual
    assert transport.calls == []


async def test_the_mismatch_message_names_neither_the_token_nor_the_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _resolver(monkeypatch, "user_delegated")
    component = build_component(SlackPostAsAppComponent, channel="C0SLACKDEMO", text="hi")

    with pytest.raises(SlackIdentityMismatchError) as raised:
        await component.build_message()

    rendered = f"{raised.value.message} {raised.value.safe_message} {raised.value.hint}"
    assert "xoxp" not in rendered
    assert "U0SLACKUSER" not in rendered


@pytest.mark.parametrize(
    ("component_class", "initial_identity", "refreshed_identity"),
    [
        (SlackPostAsAppComponent, "bot", "user_delegated"),
        (SlackSendAsUserComponent, "user_delegated", "bot"),
    ],
)
@pytest.mark.parametrize("refresh", ["auth_rejection", "expiry"])
async def test_refreshed_identity_is_checked_before_using_its_token(
    monkeypatch: pytest.MonkeyPatch,
    transport: SlackTransport,
    component_class: type,
    initial_identity: str,
    refreshed_identity: str,
    refresh: str,
) -> None:
    fake = _resolver(monkeypatch, initial_identity)
    original_resolve = fake.resolve

    async def resolve(request):
        credential = await original_resolve(request)
        if len(fake.requests) > 1:
            return replace(credential, identity=refreshed_identity)
        if refresh == "expiry":
            return replace(credential, expires_at=datetime.now(timezone.utc) + timedelta(seconds=10))
        return credential

    monkeypatch.setattr(fake, "resolve", resolve)
    if refresh == "auth_rejection":
        transport.enqueue(load_fixture("error_invalid_auth"))
    transport.enqueue(load_fixture("chat_postmessage"))
    component = build_component(component_class, channel="C0SLACKDEMO", text="hi")

    with pytest.raises(SlackIdentityMismatchError) as raised:
        await component.build_message()

    assert raised.value.expected == initial_identity
    assert raised.value.actual == refreshed_identity
    assert len(fake.requests) == 2
    assert len(transport.calls) == (1 if refresh == "auth_rejection" else 0)
