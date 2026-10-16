"""Rolling chat-history summary state shared by lfx and langflow (see Agent "Summarize Older Messages")."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # noqa: TC003
from uuid import UUID  # noqa: TC003


@dataclass(frozen=True)
class SessionMemoryState:
    """Persisted summary of messages older than the Agent's chat-history window.

    `version == 0` means no row exists yet; saves use it as a compare-and-swap token.
    """

    summary: str = ""
    cursor_message_id: UUID | None = None
    cursor_timestamp: datetime | None = None
    folded_count: int = 0
    version: int = 0
