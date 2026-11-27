"""In-memory message and session-state store for the eval.

It has the same function names and arguments as the `lfx.memory` storage functions of PR #16515, so
the vendored compressor runs unchanged. One store holds one session. Messages keep insert order, which
is the `(timestamp, id)` order of the database.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime  # noqa: TC003
from typing import Any
from uuid import UUID, uuid4

from lfx.schema.message import Message

SUMMARY_FIELDS = ("text", "sender", "session_id", "context_id", "error", "category")


def summary_snapshot(message: Any) -> dict[str, Any]:
    """The `SUMMARY_FIELDS` of a message, with missing values as None."""
    return {f: getattr(message, f, None) for f in SUMMARY_FIELDS}


@dataclass(frozen=True)
class SessionMemoryState:
    """Same shape as the PR #16515 state, plus `facts` for the Auto variants."""

    id: UUID | None = None
    summary: str = ""
    cursor_message_id: UUID | None = None
    cursor_timestamp: datetime | None = None
    folded_count: int = 0
    version: int = 0
    facts: tuple[tuple[str, str], ...] = ()


class MemStore:
    """One session: its messages, oldest first, and its state row."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.messages: list[Message] = []
        self.state = SessionMemoryState()

    def add(self, text: str, sender: str) -> Message:
        message = Message(text=text, sender=sender, sender_name=sender, session_id=self.session_id, id=str(uuid4()))
        self.messages.append(message)
        return message

    def index_of(self, message_id: Any) -> int | None:
        key = str(message_id)
        return next((i for i, m in enumerate(self.messages) if str(m.id) == key), None)

    def between(self, after_id: Any, before_id: Any, limit: int, *, newest_first: bool = False) -> list[Message]:
        """Messages strictly after `after_id` (None: from the start) and before `before_id` (None: to the end)."""
        after = None if after_id is None else self.index_of(after_id)
        start = 0 if after is None else after + 1
        end = len(self.messages) if before_id is None else self.index_of(before_id)
        if end is None:
            return []
        rows = self.messages[start:end]
        return rows[-limit:] if newest_first else rows[:limit]

    def save(
        self, *, expected_version: int, expected_state_id: UUID | None, **values: Any
    ) -> SessionMemoryState | None:
        """Compare-and-swap save, like the database version."""
        if self.state.version != expected_version or (expected_version and self.state.id != expected_state_id):
            return None
        self.state = replace(self.state, id=self.state.id or uuid4(), version=expected_version + 1, **values)
        return self.state


STORES: dict[str, MemStore] = {}


async def aget_session_memory_state(*, flow_id, user_id, session_id, context_id) -> SessionMemoryState:  # noqa: ARG001
    return STORES[session_id].state


async def aget_messages_between(
    *,
    flow_id,  # noqa: ARG001
    user_id,  # noqa: ARG001
    session_id,
    context_id,  # noqa: ARG001
    after_message_id,
    after_timestamp,  # noqa: ARG001
    before_message_id,
    limit,
    newest_first=False,
) -> list[Message]:
    return STORES[session_id].between(after_message_id, before_message_id, limit, newest_first=newest_first)


async def asave_session_memory_state(
    *,
    flow_id,  # noqa: ARG001
    user_id,  # noqa: ARG001
    session_id,
    context_id,  # noqa: ARG001
    summary,
    cursor_message_id,
    folded_delta,
    summary_model,  # noqa: ARG001
    expected_version,
    batch_snapshot,  # noqa: ARG001
    expected_state_id=None,
    facts=(),
) -> SessionMemoryState | None:
    store = STORES[session_id]
    return store.save(
        expected_version=expected_version,
        expected_state_id=expected_state_id,
        summary=summary,
        facts=tuple(tuple(pair) for pair in facts),
        cursor_message_id=cursor_message_id,
        folded_count=store.state.folded_count + folded_delta,
    )
