"""The Slack event model both tracks share: normalize, config, filters.

Everything here is pure, so these tests pin the behavior with recorded bodies
and no database; the ingress and Socket Mode suites then prove each transport
feeds these functions exactly the bodies recorded here.
"""

from __future__ import annotations

import pytest
from langflow.services.triggers.constants import KIND_SLACK_MESSAGE, KIND_SLACK_REACTION
from langflow.services.triggers.providers.slack.config import (
    InvalidSlackTriggerConfigError,
    normalize_slack_config,
)
from langflow.services.triggers.providers.slack.events import (
    PAYLOAD_KEYS,
    SlackControl,
    SlackEvent,
    normalize,
)
from langflow.services.triggers.providers.slack.filters import matches

from tests.unit.services.triggers import slack_fixtures as fx


def _event(name: str) -> SlackEvent:
    result = normalize(fx.load(name))
    assert isinstance(result, SlackEvent), name
    return result


def _message_config(**overrides) -> dict:
    return normalize_slack_config(KIND_SLACK_MESSAGE, overrides)


def _reaction_config(**overrides) -> dict:
    return normalize_slack_config(KIND_SLACK_REACTION, overrides)


# --- normalize -------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "message_channel",
        "message_thread_reply",
        "message_im",
        "message_mpim",
        "message_group",
        "app_mention",
        "reaction_added",
        "reaction_removed",
        "message_changed",
    ],
)
def test_every_supported_event_normalizes_to_the_one_payload_shape(name: str) -> None:
    event = _event(name)
    assert tuple(event.payload) == PAYLOAD_KEYS
    assert event.payload["provider"] == "slack"
    assert event.payload["slack_event_id"] == event.event_id
    assert event.dedupe_key == f"slack:{event.event_id}"
    assert event.payload["team_id"] == fx.TEAM_ID
    assert event.payload["session_key"].startswith(f"slack:{fx.TEAM_ID}:")
    assert event.payload["event"] == fx.load(name)["event"]


def test_a_top_level_message_starts_its_own_session() -> None:
    event = _event("message_channel")
    assert event.kind == KIND_SLACK_MESSAGE
    assert event.payload["session_key"] == "slack:T0TEAM0001:C0SUPPORT1:1700000000.000100"
    assert event.payload["is_thread_reply"] is False
    assert event.payload["text"] == "The nightly deploy is failing again"
    assert event.payload["user_id"] == "U0ALICE001"
    assert event.payload["channel_type"] == "channel"


def test_a_threaded_reply_joins_its_parents_session() -> None:
    parent, reply = _event("message_channel"), _event("message_thread_reply")
    assert reply.payload["is_thread_reply"] is True
    assert reply.payload["thread_ts"] == "1700000000.000100"
    assert reply.payload["session_key"] == parent.payload["session_key"]


def test_three_replies_are_three_events_in_one_session() -> None:
    events = [normalize(body) for body in fx.thread_replies(3)]
    assert len({event.dedupe_key for event in events}) == 3
    assert len({event.payload["session_key"] for event in events}) == 1


def test_a_reaction_is_scoped_to_the_message_it_reacts_to() -> None:
    event = _event("reaction_added")
    assert event.kind == KIND_SLACK_REACTION
    assert event.payload["reaction"] == "rocket"
    assert event.payload["channel_id"] == "C0RELEASE1"
    assert event.payload["item_ts"] == "1700000400.000700"
    assert event.payload["item_user_id"] == "U0ALICE001"
    assert event.payload["session_key"] == "slack:T0TEAM0001:C0RELEASE1:1700000400.000700"
    assert event.payload["text"] is None


def test_an_edit_reports_the_new_text_and_keeps_the_original_messages_session() -> None:
    event = _event("message_changed")
    assert event.payload["subtype"] == "message_changed"
    assert event.payload["text"].endswith("(edited)")
    assert event.payload["ts"] == "1700000000.000100"
    assert event.payload["session_key"] == _event("message_channel").payload["session_key"]


def test_a_deletion_reports_what_the_message_said() -> None:
    event = _event("message_deleted")
    assert event.payload["text"] == "Wrong channel, sorry"
    assert event.payload["user_id"] == "U0BOB00001"


def test_routing_facts_come_from_the_authorizations() -> None:
    event = _event("message_channel")
    assert event.team_ids == frozenset({fx.TEAM_ID})
    assert event.bot_user_ids == frozenset({fx.BOT_USER_ID})
    assert event.api_app_id == fx.APP_ID


def test_a_slack_connect_event_routes_to_the_installation_not_the_senders_workspace() -> None:
    """In a shared channel the outer ``team_id`` is where the message came from.

    That workspace may have this app installed without its bot being in the
    channel, so only the installation Slack delivered the event for routes it.
    The flow still sees where the message came from.
    """
    event = _event("message_slack_connect")
    assert event.team_ids == frozenset({fx.TEAM_ID})
    assert event.payload["team_id"] == fx.OTHER_TEAM_ID


def test_an_event_with_no_authorizations_routes_nowhere() -> None:
    body = fx.load("message_channel")
    del body["authorizations"]
    event = normalize(body)
    assert isinstance(event, SlackEvent)
    assert event.team_ids == frozenset()


def test_the_handshake_and_the_rate_limit_notice_are_controls_not_events() -> None:
    handshake = normalize(fx.load("url_verification"))
    assert handshake == SlackControl(kind="url_verification", challenge="please-echo-this-challenge-back")
    limited = normalize(fx.load("app_rate_limited"))
    assert isinstance(limited, SlackControl)
    assert limited.kind == "app_rate_limited"
    assert limited.team_id == fx.TEAM_ID


@pytest.mark.parametrize(
    "body",
    [
        fx.load("unsupported_event"),
        {"type": "event_callback", "event": {"type": "message", "channel": "C0X", "ts": "1.0"}},  # no event_id
        {"type": "event_callback", "event_id": "Ev1", "event": "not an object"},
        {"type": "block_actions"},
        {},
    ],
)
def test_anything_else_is_acknowledged_and_ignored(body: dict) -> None:
    assert normalize(body) is None


def test_a_reaction_on_a_file_is_ignored() -> None:
    body = fx.load("reaction_added")
    body["event"]["item"] = {"type": "file", "file": "F0FILE0001"}
    assert normalize(body) is None


# --- config ------------------------------------------------------------------


def test_message_config_defaults() -> None:
    assert _message_config() == {
        "channels": [],
        "conversation_types": ["channel", "group", "im", "mpim"],
        "mentions_only": False,
        "include_thread_replies": True,
        "include_bot_messages": False,
        "include_edits": False,
    }


def test_config_accepts_the_shapes_a_node_field_produces() -> None:
    config = _message_config(channels="C0SUPPORT1, C0RELEASE1\nC0SUPPORT1", conversation_types=["im", "channel"])
    assert config["channels"] == ["C0RELEASE1", "C0SUPPORT1"]
    assert config["conversation_types"] == ["channel", "im"]
    reaction = _reaction_config(emoji=[":rocket:", "White_Check_Mark"], reaction_events="both")
    assert reaction == {"channels": [], "emoji": ["rocket", "white_check_mark"], "reaction_events": "both"}


def test_config_keeps_the_keys_reconciliation_owns() -> None:
    config = normalize_slack_config(KIND_SLACK_MESSAGE, {"connection": "slack/support", "mechanism_id": "x"})
    assert config["connection"] == "slack/support"
    assert config["mechanism_id"] == "x"


@pytest.mark.parametrize(
    ("kind", "raw", "fragment"),
    [
        (KIND_SLACK_MESSAGE, {"channels": ["#support"]}, "conversation IDs"),
        (KIND_SLACK_MESSAGE, {"channels": "general"}, "conversation IDs"),
        (KIND_SLACK_MESSAGE, {"conversation_types": ["channel", "voice"]}, "Unknown conversation type"),
        (KIND_SLACK_MESSAGE, {"conversation_types": []}, "at least one conversation type"),
        (KIND_SLACK_MESSAGE, {"mentions_only": "sometimes"}, "true or false"),
        (KIND_SLACK_REACTION, {"reaction_events": "toggled"}, "reaction_events"),
        (KIND_SLACK_REACTION, {"emoji": ["party parrot!"]}, "emoji name"),
    ],
)
def test_config_that_could_never_match_is_rejected_at_save(kind: str, raw: dict, fragment: str) -> None:
    with pytest.raises(InvalidSlackTriggerConfigError, match=fragment):
        normalize_slack_config(kind, raw)


# --- filters -----------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["message_channel", "message_thread_reply", "message_im", "message_mpim", "message_group"]
)
def test_a_default_message_trigger_hears_every_conversation_type(name: str) -> None:
    assert matches(KIND_SLACK_MESSAGE, _message_config(), _event(name))


def test_a_mention_fires_a_trigger_once_not_twice() -> None:
    """Slack sends a ``message`` AND an ``app_mention`` for one mention in a channel."""
    mention, twin = _event("app_mention"), _event("message_mention_twin")
    every_message = _message_config()
    assert [matches(KIND_SLACK_MESSAGE, every_message, event) for event in (mention, twin)] == [False, True]
    mentions_only = _message_config(mentions_only=True)
    assert [matches(KIND_SLACK_MESSAGE, mentions_only, event) for event in (mention, twin)] == [True, False]


def test_the_apps_own_messages_and_reactions_never_fire_a_trigger() -> None:
    permissive = _message_config(include_bot_messages=True, include_edits=True)
    assert not matches(KIND_SLACK_MESSAGE, permissive, _event("bot_self_echo"))
    assert not matches(KIND_SLACK_REACTION, _reaction_config(reaction_events="both"), _event("reaction_by_bot"))


def test_other_bots_are_opt_in() -> None:
    event = _event("other_bot_message")
    assert not matches(KIND_SLACK_MESSAGE, _message_config(), event)
    assert matches(KIND_SLACK_MESSAGE, _message_config(include_bot_messages=True), event)


def test_edits_and_deletions_are_opt_in() -> None:
    for name in ("message_changed", "message_deleted"):
        assert not matches(KIND_SLACK_MESSAGE, _message_config(), _event(name))
        assert matches(KIND_SLACK_MESSAGE, _message_config(include_edits=True), _event(name))


def test_system_notices_never_fire_a_message_trigger() -> None:
    permissive = _message_config(include_bot_messages=True, include_edits=True)
    assert not matches(KIND_SLACK_MESSAGE, permissive, _event("message_channel_join"))


def test_thread_replies_can_be_excluded() -> None:
    config = _message_config(include_thread_replies=False)
    assert matches(KIND_SLACK_MESSAGE, config, _event("message_channel"))
    assert not matches(KIND_SLACK_MESSAGE, config, _event("message_thread_reply"))


def test_channel_and_conversation_type_filters() -> None:
    support_only = _message_config(channels=["C0SUPPORT1"])
    assert matches(KIND_SLACK_MESSAGE, support_only, _event("message_channel"))
    assert not matches(KIND_SLACK_MESSAGE, support_only, _event("message_im"))
    dms_only = _message_config(conversation_types=["im"])
    assert matches(KIND_SLACK_MESSAGE, dms_only, _event("message_im"))
    assert not matches(KIND_SLACK_MESSAGE, dms_only, _event("message_mpim"))


def test_reaction_filters() -> None:
    added, removed = _event("reaction_added"), _event("reaction_removed")
    default = _reaction_config()
    assert matches(KIND_SLACK_REACTION, default, added)
    assert not matches(KIND_SLACK_REACTION, default, removed)
    both = _reaction_config(reaction_events="both")
    assert matches(KIND_SLACK_REACTION, both, removed)
    rocket = _reaction_config(emoji=["rocket"], channels=["C0RELEASE1"])
    assert matches(KIND_SLACK_REACTION, rocket, added)
    assert not matches(KIND_SLACK_REACTION, _reaction_config(emoji=["tada"]), added)
    assert not matches(KIND_SLACK_REACTION, _reaction_config(channels=["C0SUPPORT1"]), added)


def test_a_skin_toned_reaction_matches_its_emoji() -> None:
    assert matches(KIND_SLACK_REACTION, _reaction_config(emoji=["thumbsup"]), _event("reaction_skin_tone"))


def test_a_message_never_fires_a_reaction_trigger_and_vice_versa() -> None:
    assert not matches(KIND_SLACK_REACTION, _reaction_config(), _event("message_channel"))
    assert not matches(KIND_SLACK_MESSAGE, _message_config(), _event("reaction_added"))
