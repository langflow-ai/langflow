"""The stored configuration of a Slack trigger, and its validation.

A Slack trigger node's fields are copied onto ``trigger.config`` on every flow
save. This module turns the raw node values into the one normalized shape both
the Events API fan-out and the Socket Mode adapter filter with, and rejects what
could never match - so a typo is reported when the flow is saved, not
discovered as silence a week later.
"""

from __future__ import annotations

import re
from typing import Any

from langflow.services.triggers.constants import KIND_SLACK_MESSAGE, KIND_SLACK_REACTION

CONVERSATION_TYPES = ("channel", "group", "im", "mpim")
REACTION_EVENTS = ("added", "removed", "both")

#: Slack conversation ids: public/private channels ``C``, legacy private
#: channels and group DMs ``G``, direct messages ``D``.
_CHANNEL_ID = re.compile(r"^[CGD][A-Z0-9]{2,}$")
#: Emoji short names as Slack reports them in ``reaction`` (no colons).
_EMOJI = re.compile(r"^[a-z0-9_+'\-]+$")
_SEPARATORS = re.compile(r"[\s,]+")

MESSAGE_DEFAULTS: dict[str, Any] = {
    "channels": [],
    "conversation_types": list(CONVERSATION_TYPES),
    "mentions_only": False,
    "include_thread_replies": True,
    "include_bot_messages": False,
    "include_edits": False,
}
REACTION_DEFAULTS: dict[str, Any] = {
    "channels": [],
    "emoji": [],
    "reaction_events": "added",
}


class InvalidSlackTriggerConfigError(ValueError):
    """A Slack trigger node is configured in a way that can never match an event."""


def normalize_slack_config(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Return the stored config for a Slack trigger node, or raise.

    Keys this module does not own (``connection``, ``mechanism_id``) are carried
    through untouched; reconciliation owns those.
    """
    if kind == KIND_SLACK_MESSAGE:
        normalized = _message(raw)
    elif kind == KIND_SLACK_REACTION:
        normalized = _reaction(raw)
    else:  # pragma: no cover - callers dispatch on SLACK_TRIGGER_KINDS
        msg = f"Not a Slack trigger kind: {kind!r}"
        raise InvalidSlackTriggerConfigError(msg)
    passthrough = {key: value for key, value in raw.items() if key not in normalized}
    return {**passthrough, **normalized}


def _message(raw: dict[str, Any]) -> dict[str, Any]:
    types = _list(raw.get("conversation_types"), default=MESSAGE_DEFAULTS["conversation_types"])
    unknown = sorted(set(types) - set(CONVERSATION_TYPES))
    if unknown:
        msg = f"Unknown conversation type(s) {unknown}; choose from {list(CONVERSATION_TYPES)}."
        raise InvalidSlackTriggerConfigError(msg)
    if not types:
        msg = "Choose at least one conversation type, or the trigger can never fire."
        raise InvalidSlackTriggerConfigError(msg)
    return {
        "channels": _channels(raw.get("channels")),
        # Stable order, so an unchanged node never rewrites the row.
        "conversation_types": [value for value in CONVERSATION_TYPES if value in types],
        "mentions_only": _bool(raw.get("mentions_only"), default=MESSAGE_DEFAULTS["mentions_only"]),
        "include_thread_replies": _bool(
            raw.get("include_thread_replies"), default=MESSAGE_DEFAULTS["include_thread_replies"]
        ),
        "include_bot_messages": _bool(
            raw.get("include_bot_messages"), default=MESSAGE_DEFAULTS["include_bot_messages"]
        ),
        "include_edits": _bool(raw.get("include_edits"), default=MESSAGE_DEFAULTS["include_edits"]),
    }


def _reaction(raw: dict[str, Any]) -> dict[str, Any]:
    events = raw.get("reaction_events") or REACTION_DEFAULTS["reaction_events"]
    if events not in REACTION_EVENTS:
        msg = f"reaction_events must be one of {list(REACTION_EVENTS)}, not {events!r}."
        raise InvalidSlackTriggerConfigError(msg)
    emoji = [value.strip(":").lower() for value in _list(raw.get("emoji"), default=[])]
    bad = [value for value in emoji if not _EMOJI.match(value)]
    if bad:
        msg = f"Not an emoji name: {bad}. Use short names such as 'rocket' or 'white_check_mark'."
        raise InvalidSlackTriggerConfigError(msg)
    return {
        "channels": _channels(raw.get("channels")),
        "emoji": sorted(set(emoji)),
        "reaction_events": events,
    }


def _channels(value: Any) -> list[str]:
    # Matched as given: Slack ids are upper-case, and upper-casing input would
    # quietly turn a channel *name* such as ``general`` into an id-shaped
    # ``GENERAL`` that can never match.
    channels = _list(value, default=[])
    bad = [item for item in channels if not _CHANNEL_ID.match(item)]
    if bad:
        msg = (
            f"Channels must be Slack conversation IDs such as C0123456789, not names: {bad}. "
            "Find an ID under the channel's details, or leave the list empty for every channel the app is in."
        )
        raise InvalidSlackTriggerConfigError(msg)
    return sorted(set(channels))


def _list(value: Any, *, default: list[str]) -> list[str]:
    if value is None or value == "":
        return list(default)
    if isinstance(value, str):
        items = _SEPARATORS.split(value)
    elif isinstance(value, list | tuple):
        items = [part for item in value if isinstance(item, str) for part in _SEPARATORS.split(item)]
    else:
        msg = f"Expected a list of values, got {type(value).__name__}."
        raise InvalidSlackTriggerConfigError(msg)
    return [item.strip() for item in items if item.strip()]


def _bool(value: Any, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    msg = f"Expected true or false, got {value!r}."
    raise InvalidSlackTriggerConfigError(msg)
