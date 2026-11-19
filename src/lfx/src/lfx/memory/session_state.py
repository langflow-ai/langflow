"""Rolling chat-history summary state shared by lfx and langflow (see Agent "Summarize Older Messages")."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # noqa: TC003
from typing import Any
from uuid import UUID  # noqa: TC003

# Message fields a fold reads (text, sender) or filters on (session, context, error, category). One list, used to
# snapshot a batch before it is summarized and to detect edits and moves of stored messages.
SUMMARY_FIELDS = ("text", "sender", "session_id", "context_id", "error", "category")


def summary_snapshot(message: Any) -> dict[str, Any]:
    """The `SUMMARY_FIELDS` of a message, with missing values as None."""
    return {field: getattr(message, field, None) for field in SUMMARY_FIELDS}


@dataclass(frozen=True)
class SessionMemoryState:
    """Persisted summary of messages older than the Agent's chat-history window.

    `version == 0` means no row exists yet. Saves use `id` and `version` together as the compare-and-swap
    token: a row that was reset and re-created has a new `id`, so an older fold cannot overwrite it.
    """

    id: UUID | None = None
    summary: str = ""
    cursor_message_id: UUID | None = None
    cursor_timestamp: datetime | None = None
    folded_count: int = 0
    version: int = 0
