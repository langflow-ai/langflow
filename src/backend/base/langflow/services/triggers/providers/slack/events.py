"""Normalize a Slack Events API body into the Data a triggered flow receives.

The Events API POST body and the ``payload`` of a Socket Mode ``events_api``
envelope are the same document, so this module is the single place that
document is read. Everything here is pure: no I/O and no clock, which is what
lets the cross-track contract test demand byte-identical output.

The flow-facing payload has one fixed shape for every event type, with ``None``
where a field does not apply, so a flow can read ``text`` or ``reaction``
without first asking which event fired it. It carries the raw inner ``event``
object as well, for anything the normalized fields leave out.

Delivery metadata (``X-Slack-Retry-Num``, ``envelope_id``, ``retry_attempt``)
is deliberately not part of it: it differs between the two tracks and between
retries of one event, and the payload must not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from langflow.services.triggers.constants import (
    DEDUPE_PREFIX_SLACK,
    KIND_SLACK_MESSAGE,
    KIND_SLACK_REACTION,
    PROVIDER_SLACK,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

EVENT_MESSAGE = "message"
EVENT_APP_MENTION = "app_mention"
EVENT_REACTION_ADDED = "reaction_added"
EVENT_REACTION_REMOVED = "reaction_removed"

#: Slack event type -> the trigger kind it can fire.
EVENT_KINDS: dict[str, str] = {
    EVENT_MESSAGE: KIND_SLACK_MESSAGE,
    EVENT_APP_MENTION: KIND_SLACK_MESSAGE,
    EVENT_REACTION_ADDED: KIND_SLACK_REACTION,
    EVENT_REACTION_REMOVED: KIND_SLACK_REACTION,
}

#: Message subtypes whose visible content lives in a nested object.
SUBTYPE_MESSAGE_CHANGED = "message_changed"
SUBTYPE_MESSAGE_DELETED = "message_deleted"

#: Keys of the flow-facing payload, in the order they are written.
PAYLOAD_KEYS = (
    "provider",
    "session_key",
    "slack_event_id",
    "event_time",
    "team_id",
    "api_app_id",
    "type",
    "subtype",
    "channel_id",
    "channel_type",
    "user_id",
    "bot_id",
    "text",
    "ts",
    "thread_ts",
    "is_thread_reply",
    "reaction",
    "item_ts",
    "item_user_id",
    "event",
)


@dataclass(frozen=True)
class SlackControl:
    """A body that is about the delivery channel itself, never a flow run.

    ``url_verification`` is the Request URL handshake: its ``challenge`` is
    echoed and nothing is written. ``app_rate_limited`` is Slack reporting that
    the app passed the 30,000-events-per-workspace-per-hour ceiling; it is
    acknowledged and audited so an operator can see why events stopped.
    """

    kind: Literal["url_verification", "app_rate_limited"]
    challenge: str | None = None
    team_id: str | None = None
    minute_rate_limited: int | None = None


@dataclass(frozen=True)
class SlackEvent:
    """One normalized event, ready to be matched against triggers.

    ``team_ids`` and ``bot_user_ids`` are routing facts, not flow data: the
    installation(s) the event was delivered for, and the app's own bot users, so
    a flow that replies in a thread does not trigger itself.
    """

    event_id: str
    kind: str
    dedupe_key: str
    team_ids: frozenset[str]
    bot_user_ids: frozenset[str]
    api_app_id: str | None
    payload: dict[str, Any]

    @property
    def event_type(self) -> str:
        return self.payload["type"]


def dedupe_key(event_id: str) -> str:
    """The ledger key for a Slack event, identical on both tracks.

    ``event_id`` is stable across the Events API's three retries and across a
    Socket Mode redelivery, so it collapses every copy of one event to one row
    per trigger whichever transport - or both, during a move between them -
    carried it.
    """
    return f"{DEDUPE_PREFIX_SLACK}:{event_id}"


def session_key(team_id: str | None, channel_id: str | None, conversation_ts: str | None) -> str | None:
    """``slack:{team_id}:{channel}:{thread_ts or ts}`` (trigger contract section 4).

    A threaded reply names its parent's ``ts``, so every reply in a thread lands
    in the parent's session; a new top-level message starts its own.
    """
    if not (team_id and channel_id and conversation_ts):
        return None
    return f"{PROVIDER_SLACK}:{team_id}:{channel_id}:{conversation_ts}"


def normalize(body: Mapping[str, Any]) -> SlackEvent | SlackControl | None:
    """Read one Events API body. ``None`` means "acknowledge and ignore".

    Ignored: any envelope type other than ``event_callback`` and the two
    controls; event types no trigger subscribes to; an ``event_callback`` with
    no ``event_id`` (it could never be deduplicated); and reactions on anything
    but a message (legacy file reactions have no channel to scope them to).
    """
    envelope_type = body.get("type")
    if envelope_type == "url_verification":
        challenge = body.get("challenge")
        return SlackControl(kind="url_verification", challenge=challenge if isinstance(challenge, str) else None)
    if envelope_type == "app_rate_limited":
        minute = body.get("minute_rate_limited")
        return SlackControl(
            kind="app_rate_limited",
            team_id=_str(body.get("team_id")),
            minute_rate_limited=minute if isinstance(minute, int) else None,
        )
    if envelope_type != "event_callback":
        return None

    event = body.get("event")
    event_id = _str(body.get("event_id"))
    if not isinstance(event, dict) or not event_id:
        return None
    event_type = event.get("type")
    kind = EVENT_KINDS.get(event_type) if isinstance(event_type, str) else None
    if kind is None:
        return None

    team_id = _str(body.get("team_id"))
    fields = _reaction_fields(event) if kind == KIND_SLACK_REACTION else _message_fields(event)
    if fields is None:
        return None

    conversation_ts = fields.pop("_conversation_ts")
    payload: dict[str, Any] = dict.fromkeys(PAYLOAD_KEYS)
    payload.update(fields)
    payload.update(
        {
            "provider": PROVIDER_SLACK,
            "session_key": session_key(team_id, payload["channel_id"], conversation_ts),
            "slack_event_id": event_id,
            "event_time": body.get("event_time") if isinstance(body.get("event_time"), int) else None,
            "team_id": team_id,
            "api_app_id": _str(body.get("api_app_id")),
            "type": event_type,
            "event": event,
        }
    )
    authorizations = [entry for entry in body.get("authorizations") or [] if isinstance(entry, dict)]
    return SlackEvent(
        event_id=event_id,
        kind=kind,
        dedupe_key=dedupe_key(event_id),
        team_ids=frozenset(filter(None, [team_id, *(_str(entry.get("team_id")) for entry in authorizations)])),
        bot_user_ids=frozenset(
            filter(None, (_str(entry.get("user_id")) for entry in authorizations if entry.get("is_bot") is True))
        ),
        api_app_id=payload["api_app_id"],
        payload=payload,
    )


def _message_fields(event: Mapping[str, Any]) -> dict[str, Any] | None:
    """Fields of a ``message`` or ``app_mention`` event.

    An edit carries the new message under ``message`` and a deletion the old one
    under ``previous_message``; the visible content is read from there so the
    flow sees what the message says (or said), not the envelope around it.
    """
    subtype = _str(event.get("subtype"))
    visible: Mapping[str, Any] = event
    if subtype == SUBTYPE_MESSAGE_CHANGED and isinstance(event.get("message"), dict):
        visible = event["message"]
    elif subtype == SUBTYPE_MESSAGE_DELETED and isinstance(event.get("previous_message"), dict):
        visible = event["previous_message"]

    channel_id = _str(event.get("channel"))
    ts = _str(visible.get("ts")) or _str(event.get("ts"))
    thread_ts = _str(visible.get("thread_ts"))
    if not channel_id or not ts:
        return None
    return {
        "subtype": subtype,
        "channel_id": channel_id,
        "channel_type": _str(event.get("channel_type")),
        "user_id": _str(visible.get("user")),
        "bot_id": _str(visible.get("bot_id")),
        "text": visible.get("text") if isinstance(visible.get("text"), str) else None,
        "ts": ts,
        "thread_ts": thread_ts,
        "is_thread_reply": bool(thread_ts and thread_ts != ts),
        "_conversation_ts": thread_ts or ts,
    }


def _reaction_fields(event: Mapping[str, Any]) -> dict[str, Any] | None:
    """Fields of a ``reaction_added`` / ``reaction_removed`` event.

    The session is the reacted-to message's own ``ts``. The event does not say
    whether that message is a threaded reply (only a fetch-back could, and
    ingress never calls out), so a reaction on a reply correlates with the reply
    rather than with its thread's parent.
    """
    item = event.get("item")
    if not isinstance(item, dict) or item.get("type") != "message":
        return None
    channel_id = _str(item.get("channel"))
    item_ts = _str(item.get("ts"))
    if not channel_id or not item_ts:
        return None
    return {
        "channel_id": channel_id,
        "user_id": _str(event.get("user")),
        "ts": _str(event.get("event_ts")),
        "reaction": _str(event.get("reaction")),
        "item_ts": item_ts,
        "item_user_id": _str(event.get("item_user")),
        "is_thread_reply": False,
        "_conversation_ts": item_ts,
    }


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
