"""Identity mismatches fail closed before the first Slack request.

Slack user and bot tokens share scope names, so ``granted_scopes`` cannot tell
them apart. Without this guard, the first signal that a bot action was handed a
user connection would be Slack's own ``not_allowed_token_type`` -- after the
request left the process.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from conftest import FakeResolver, SlackTransport, build_component, load_fixture
from lfx.integrations.errors import ConnectionNotAuthorizedError
from lfx_slack import SlackPostAsAppComponent, SlackSearchComponent, SlackSendAsUserComponent
from lfx_slack._base import SlackIdentityMismatchError


def _resolver(monkeypatch: pytest.MonkeyPatch, identity: str | None) -> FakeResolver:
    fake = FakeResolver(identity=identity)
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


async def test_a_headless_credential_without_an_identity_is_trusted(
    monkeypatch: pytest.MonkeyPatch,
    transport: SlackTransport,
) -> None:
    """LF_CONNECTION__SLACK__* has no place to declare an identity."""
    _resolver(monkeypatch, None)
    transport.enqueue(load_fixture("chat_postmessage"))
    component = build_component(SlackPostAsAppComponent, channel="C0SLACKDEMO", text="hi")

    message = await component.build_message()

    assert message.data["ts"] == "1700000200.000400"
    assert len(transport.calls) == 1


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
