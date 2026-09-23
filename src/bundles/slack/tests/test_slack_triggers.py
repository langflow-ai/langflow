"""The two Slack trigger nodes: what they declare, and what they hand the flow.

A trigger node is a declaration. The server decides the transport, receives the
events and writes the ledger; these tests pin the node's side of that contract -
its kind, its configuration fields, and the Data and Message it produces from
the event the dispatcher attaches to a run.
"""

from __future__ import annotations

import json

import pytest
from conftest import FakeResolver, build_component
from lfx.base.triggers.base import TRIGGER_EVENT_FIELD, BaseTriggerComponent
from lfx_slack import SlackOnMessageTriggerComponent, SlackOnReactionTriggerComponent, SlackPostAsAppComponent
from lfx_slack._base import SlackAppLevelTokenError

MESSAGE_EVENT = {
    "trigger_id": "4f8e3f9e-0000-0000-0000-000000000001",
    "event_id": "4f8e3f9e-0000-0000-0000-000000000002",
    "kind": "slack.message",
    "provider": "slack",
    "dedupe_key": "slack:Ev0MSG00001",
    "attempt": 1,
    "payload": {
        "provider": "slack",
        "session_key": "slack:T0TEAM0001:C0SUPPORT1:1700000000.000100",
        "slack_event_id": "Ev0MSG00001",
        "type": "message",
        "channel_id": "C0SUPPORT1",
        "user_id": "U0ALICE001",
        "text": "The nightly deploy is failing again",
        "ts": "1700000000.000100",
        "thread_ts": None,
    },
}


@pytest.mark.parametrize(
    ("component_class", "kind"),
    [(SlackOnMessageTriggerComponent, "slack.message"), (SlackOnReactionTriggerComponent, "slack.reaction")],
)
def test_each_node_declares_a_provider_trigger_that_needs_a_connection(component_class, kind: str) -> None:
    assert issubclass(component_class, BaseTriggerComponent)
    definition = build_component(component_class).trigger_definition()

    assert definition.kind == kind
    assert definition.provider == "slack"
    assert definition.needs_connection is True
    assert definition.config["connection"] == "slack/workspace"


def test_the_nodes_follow_the_trigger_naming_rule() -> None:
    """``Product: On Event`` (design/dedicated-integrations-triggers/frontend-surfaces.md)."""
    assert SlackOnMessageTriggerComponent.display_name == "Slack: On Message"
    assert SlackOnReactionTriggerComponent.display_name == "Slack: On Reaction"


def test_the_event_field_is_prepended_for_the_dispatcher() -> None:
    for component_class in (SlackOnMessageTriggerComponent, SlackOnReactionTriggerComponent):
        assert component_class.inputs[0].name == TRIGGER_EVENT_FIELD


def test_the_message_trigger_declares_its_filters() -> None:
    component = build_component(
        SlackOnMessageTriggerComponent,
        channels=["C0SUPPORT1"],
        mentions_only=True,
        conversation_types=["channel"],
    )
    config = component.trigger_config()

    assert config["channels"] == ["C0SUPPORT1"]
    assert config["mentions_only"] is True
    assert config["conversation_types"] == ["channel"]
    assert set(config) == {
        "connection",
        "channels",
        "conversation_types",
        "mentions_only",
        "include_thread_replies",
        "include_bot_messages",
        "include_edits",
    }


def test_the_reaction_trigger_declares_its_filters() -> None:
    config = build_component(SlackOnReactionTriggerComponent, emoji=["rocket"], reaction_events="both").trigger_config()

    assert config == {"connection": "slack/workspace", "channels": [], "emoji": ["rocket"], "reaction_events": "both"}


def test_a_triggered_run_hands_the_flow_the_event_and_its_text() -> None:
    component = build_component(SlackOnMessageTriggerComponent, **{TRIGGER_EVENT_FIELD: json.dumps(MESSAGE_EVENT)})

    event = component.build_event()
    message = component.build_message()

    assert event.data == MESSAGE_EVENT
    assert event.data["payload"]["session_key"] == "slack:T0TEAM0001:C0SUPPORT1:1700000000.000100"
    assert message.text == "The nightly deploy is failing again"


def test_a_manual_run_yields_an_empty_event_rather_than_failing() -> None:
    component = build_component(SlackOnMessageTriggerComponent)

    assert component.build_event().data == {}
    assert component.build_message().text == ""


def test_the_trigger_nodes_never_resolve_their_connection() -> None:
    """The server holds the socket or the Request URL; the node only reads the event it was handed."""
    component = build_component(SlackOnMessageTriggerComponent, **{TRIGGER_EVENT_FIELD: json.dumps(MESSAGE_EVENT)})

    def _refuse(_field):
        msg = "a trigger node must not resolve its connection"
        raise AssertionError(msg)

    component.resolve_connection = _refuse
    component.build_event()
    component.build_message()


async def test_an_action_refuses_an_app_level_token(monkeypatch: pytest.MonkeyPatch, transport) -> None:
    """An app-level token opens Socket Mode sockets and can call no Web API method.

    It is recorded with the app's ``bot`` identity and has no ``xoxb-`` prefix, so
    without the explicit check a bot action would accept it.
    """
    fake = FakeResolver(identity="bot", tokens=["xapp-1-A0APP00001-1-token"])  # pragma: allowlist secret
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: fake)
    component = build_component(SlackPostAsAppComponent, channel="C0SUPPORT1", text="hello")

    with pytest.raises(SlackAppLevelTokenError, match="app-level token"):
        await component.build_message()
    assert transport.calls == []
