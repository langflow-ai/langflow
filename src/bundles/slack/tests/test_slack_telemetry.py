"""Slack action observability stays low-cardinality and credential-free."""

from __future__ import annotations

import pytest
from conftest import FakeResolver, SlackTransport, build_component, load_fixture
from lfx.integrations.errors import ScopeMissingError
from lfx_slack import SlackPostAsAppComponent, SlackSearchComponent
from lfx_slack._base import SlackBaseComponent, SlackIdentityMismatchError


@pytest.fixture
def observability(monkeypatch: pytest.MonkeyPatch) -> list:
    captured: list = []

    original_log = SlackBaseComponent.log

    def capture_log(component, message, name=None):
        original_log(component, message, name)
        captured.append(component._logs[-1].message)

    monkeypatch.setattr(SlackBaseComponent, "log", capture_log)
    return captured


@pytest.fixture
def user_resolver(monkeypatch: pytest.MonkeyPatch) -> FakeResolver:
    fake = FakeResolver(identity="user_delegated", tokens=["xoxp-user-token"])  # pragma: allowlist secret
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: fake)
    return fake


@pytest.mark.usefixtures("user_resolver")
async def test_a_successful_action_reports_only_the_capability(
    transport: SlackTransport,
    observability: list,
) -> None:
    transport.enqueue(load_fixture("search_messages"))
    component = build_component(SlackSearchComponent, query="deploy")

    await component.build_matches()

    rendered = observability[0]
    assert rendered["provider"] == "slack"
    assert rendered["capability"] == "slack.user.search"
    assert rendered["success"] is True
    assert rendered["error_code"] is None
    assert "connection" not in rendered
    for value in rendered.values():
        assert value != "xoxp-user-token"
        assert value != "U0SLACKUSER"


@pytest.mark.usefixtures("user_resolver")
async def test_a_failed_action_reports_the_typed_error_code(
    transport: SlackTransport,
    observability: list,
) -> None:
    transport.enqueue(load_fixture("error_missing_scope"))
    component = build_component(SlackSearchComponent, query="deploy")

    with pytest.raises(ScopeMissingError):
        await component.build_matches()

    payload = observability[0]
    assert payload["success"] is False
    assert payload["error_code"] == "scope-missing"


@pytest.mark.usefixtures("user_resolver", "transport")
async def test_a_fail_closed_identity_denial_is_recorded(observability: list) -> None:
    """The denial an operator most wants counted must not fall outside the span."""
    component = build_component(SlackPostAsAppComponent, channel="C0SLACKDEMO", text="hi")

    with pytest.raises(SlackIdentityMismatchError):
        await component.build_message()

    payload = observability[0]
    assert payload["provider"] == "slack"
    assert payload["capability"] == "slack.bot.post"
    assert payload["success"] is False
    assert payload["error_code"] == "connection-not-authorized"
