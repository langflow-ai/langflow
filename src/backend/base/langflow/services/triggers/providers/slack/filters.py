"""Does one normalized Slack event fire one trigger?

Pure, and shared by both tracks: the Events API fan-out and the Socket Mode
adapter call the same function with the same stored config, which is half of
what makes "the same flow runs the same on either transport" true (the other
half is :mod:`events`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langflow.services.triggers.constants import KIND_SLACK_MESSAGE, KIND_SLACK_REACTION
from langflow.services.triggers.providers.slack.config import MESSAGE_DEFAULTS, REACTION_DEFAULTS
from langflow.services.triggers.providers.slack.events import (
    EVENT_APP_MENTION,
    EVENT_MESSAGE,
    EVENT_REACTION_ADDED,
    EVENT_REACTION_REMOVED,
    SUBTYPE_MESSAGE_CHANGED,
    SUBTYPE_MESSAGE_DELETED,
    SlackEvent,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

#: Message subtypes that are a person saying something. System notices
#: (``channel_join``, ``channel_topic``, ``pinned_item``, ...) never fire a
#: trigger: nobody writes "when someone joins #support, triage it" as a message
#: trigger, and letting them through would run a flow per membership change.
_CONVERSATIONAL_SUBTYPES = frozenset({None, "thread_broadcast", "file_share", "me_message"})
_EDIT_SUBTYPES = frozenset({SUBTYPE_MESSAGE_CHANGED, SUBTYPE_MESSAGE_DELETED})
_BOT_SUBTYPE = "bot_message"

_REACTION_EVENT_TYPES = {
    "added": frozenset({EVENT_REACTION_ADDED}),
    "removed": frozenset({EVENT_REACTION_REMOVED}),
    "both": frozenset({EVENT_REACTION_ADDED, EVENT_REACTION_REMOVED}),
}


def matches(kind: str, config: Mapping[str, Any], event: SlackEvent) -> bool:
    """True when ``event`` should fire a trigger of ``kind`` configured with ``config``."""
    if event.kind != kind or is_self_echo(event):
        return False
    channels = config.get("channels") or []
    if channels and event.payload["channel_id"] not in channels:
        return False
    if kind == KIND_SLACK_MESSAGE:
        return _message_matches(config, event)
    if kind == KIND_SLACK_REACTION:
        return _reaction_matches(config, event)
    return False


def is_self_echo(event: SlackEvent) -> bool:
    """The event was caused by this app's own bot.

    Always dropped, whatever the node says: a flow that replies in a thread or
    adds a reaction would otherwise trigger itself, forever. Recognized by the
    bot user the event was delivered for, or by the app id Slack stamps on a
    message an app posted.
    """
    payload = event.payload
    if payload["user_id"] and payload["user_id"] in event.bot_user_ids:
        return True
    raw = payload.get("event") or {}
    visible = raw.get("message") if isinstance(raw.get("message"), dict) else raw
    app_ids = {visible.get("app_id"), (visible.get("bot_profile") or {}).get("app_id")}
    return bool(event.api_app_id) and event.api_app_id in app_ids


def _message_matches(config: Mapping[str, Any], event: SlackEvent) -> bool:
    payload = event.payload
    mentions_only = config.get("mentions_only", MESSAGE_DEFAULTS["mentions_only"])
    # Slack sends BOTH a ``message`` and an ``app_mention`` event for a mention
    # in a channel the app reads. Taking exactly one of them per trigger is what
    # keeps a mention from running the flow twice.
    wanted = EVENT_APP_MENTION if mentions_only else EVENT_MESSAGE
    if payload["type"] != wanted:
        return False

    subtype = payload["subtype"]
    include_bots = config.get("include_bot_messages", MESSAGE_DEFAULTS["include_bot_messages"])
    include_edits = config.get("include_edits", MESSAGE_DEFAULTS["include_edits"])
    allowed = set(_CONVERSATIONAL_SUBTYPES)
    if include_bots:
        allowed.add(_BOT_SUBTYPE)
    if include_edits:
        allowed |= _EDIT_SUBTYPES
    if subtype not in allowed:
        return False
    if not include_bots and payload["bot_id"]:
        return False

    if payload["is_thread_reply"] and not config.get(
        "include_thread_replies", MESSAGE_DEFAULTS["include_thread_replies"]
    ):
        return False

    # ``app_mention`` carries no channel_type. Older stored configs may still
    # narrow types with mentions_only, so fail closed rather than firing in an
    # excluded conversation.
    channel_type = payload["channel_type"]
    types = config.get("conversation_types") or MESSAGE_DEFAULTS["conversation_types"]
    if channel_type is None:
        return set(types) == set(MESSAGE_DEFAULTS["conversation_types"])
    return channel_type in types


def _reaction_matches(config: Mapping[str, Any], event: SlackEvent) -> bool:
    payload = event.payload
    events = _REACTION_EVENT_TYPES.get(config.get("reaction_events") or REACTION_DEFAULTS["reaction_events"])
    if not events or payload["type"] not in events:
        return False
    emoji = config.get("emoji") or []
    # A skin-toned reaction arrives as ``thumbsup::skin-tone-2``; the filter
    # names the emoji, not the tone.
    reaction = (payload["reaction"] or "").split("::", 1)[0]
    return not emoji or reaction in emoji
