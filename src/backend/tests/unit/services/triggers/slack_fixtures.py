"""Load the recorded Slack Events API bodies and wrap them for Socket Mode.

Kept as a plain module (not a conftest) so the API tests, the adapter tests and
the cross-track contract test all read the same files the same way.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures" / "slack"

TEAM_ID = "T0TEAM0001"
OTHER_TEAM_ID = "T0TEAM0002"
APP_ID = "A0APP00001"
BOT_USER_ID = "U0BOT00001"


def load(name: str) -> dict[str, Any]:
    """A fresh copy of one recorded body, so a test may mutate it freely."""
    return json.loads((FIXTURES / f"{name}.json").read_text())


def names() -> list[str]:
    return sorted(path.stem for path in FIXTURES.glob("*.json"))


def raw(name: str) -> bytes:
    """The body exactly as it would be POSTed: the bytes a signature covers."""
    return json.dumps(load(name), separators=(",", ":")).encode()


def socket_envelope(body: dict[str, Any], *, envelope_id: str, retry_attempt: int = 0) -> dict[str, Any]:
    """The Socket Mode frame that carries ``body`` (https://docs.slack.dev/apis/socket-mode/)."""
    return {
        "envelope_id": envelope_id,
        "type": "events_api",
        "accepts_response_payload": False,
        "retry_attempt": retry_attempt,
        "retry_reason": "timeout" if retry_attempt else "",
        "payload": copy.deepcopy(body),
    }


def thread_replies(count: int) -> list[dict[str, Any]]:
    """``count`` distinct replies in one thread (distinct ``event_id`` and ``ts``)."""
    replies = []
    for index in range(count):
        body = load("message_thread_reply")
        body["event_id"] = f"Ev0THR{index:05d}"
        body["event"]["ts"] = body["event"]["event_ts"] = f"17000010{index:02d}.000{index:03d}"
        body["event"]["text"] = f"reply {index + 1}"
        replies.append(body)
    return replies
