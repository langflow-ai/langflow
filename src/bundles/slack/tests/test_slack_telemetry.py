"""Slack action telemetry stays low-cardinality and credential-free."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from conftest import FakeResolver, SlackTransport, build_component, load_fixture
from lfx.integrations.errors import ScopeMissingError
from lfx.services.schema import ServiceType
from lfx_slack import SlackSearchComponent


@pytest.fixture
def telemetry(monkeypatch: pytest.MonkeyPatch) -> list:
    captured: list = []

    class Telemetry:
        async def send_telemetry_data(self, payload, event_name):
            captured.append((payload, event_name))

    manager = SimpleNamespace(services={ServiceType.TELEMETRY_SERVICE: Telemetry()})
    monkeypatch.setattr("lfx.services.manager.get_service_manager", lambda: manager)
    return captured


@pytest.fixture
def user_resolver(monkeypatch: pytest.MonkeyPatch) -> FakeResolver:
    fake = FakeResolver(identity="user_delegated", tokens=["xoxp-user-token"])  # pragma: allowlist secret
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: fake)
    return fake


@pytest.mark.usefixtures("user_resolver")
async def test_a_successful_action_reports_only_the_capability(
    transport: SlackTransport,
    telemetry: list,
) -> None:
    transport.enqueue(load_fixture("search_messages"))
    component = build_component(SlackSearchComponent, query="deploy")

    await component.build_matches()

    payload, event_name = telemetry[0]
    rendered = payload.model_dump()
    assert event_name == "integration_action"
    assert rendered["provider"] == "slack"
    assert rendered["capability"] == "slack.user.search"
    assert rendered["success"] is True
    assert rendered["error_code"] is None
    assert rendered["owner_kind"] == "user"
    assert "connection" not in rendered
    for value in rendered.values():
        assert value != "xoxp-user-token"
        assert value != "U0SLACKUSER"


@pytest.mark.usefixtures("user_resolver")
async def test_a_failed_action_reports_the_typed_error_code(
    transport: SlackTransport,
    telemetry: list,
) -> None:
    transport.enqueue(load_fixture("error_missing_scope"))
    component = build_component(SlackSearchComponent, query="deploy")

    with pytest.raises(ScopeMissingError):
        await component.build_matches()

    payload, _ = telemetry[0]
    assert payload.success is False
    assert payload.error_code == "scope-missing"
