"""Per-session conversation memory for the Langflow Assistant.

The frontend has no concept of conversation history at the request level —
each ``/api/v1/agentic/assist/stream`` call sends only ``input_value`` and a
``session_id``. Without buffering on the backend, the LLM has no memory of
prior turns, so the user has to repeat themselves any time they refine a
build or ask a follow-up.

This module keeps a process-local cache of the last few turns per session:
    - Per-session ring buffer (``MAX_TURNS_PER_SESSION`` entries, FIFO).
    - Cross-session LRU cap (``MAX_SESSIONS``) so a process that handles
      thousands of distinct sessions doesn't grow unbounded.
    - Asyncio-aware lock for concurrent ``push_async`` calls hitting the
      same session.

History is volatile by design — it lives in memory only, not in the
database. A process restart wipes it; a horizontally scaled deployment
will have per-replica history (good enough for the assistant's UX, and
sidesteps the privacy concern of persisting LLM exchanges to durable
storage without an explicit user opt-in).
"""

from __future__ import annotations

import asyncio
import os
from collections import OrderedDict, deque
from dataclasses import dataclass

MAX_TURNS_PER_SESSION = 10
MAX_SESSIONS = 100
HISTORY_TURN_LIMIT = 6
MAX_TURN_FIELD_CHARS = 2000


def history_turn_limit() -> int:
    """Turns injected into the prompt per request (buffer retention is separate).

    The injected block is re-sent on EVERY agent iteration, so it is a direct
    per-turn cost multiplier — bounded by default, env-tunable for users who
    want longer memory and accept the token cost.
    """
    raw = os.environ.get("LANGFLOW_ASSISTANT_HISTORY_TURNS", "")
    try:
        return max(0, int(raw))
    except ValueError:
        return HISTORY_TURN_LIMIT


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n... [truncated]"


@dataclass(frozen=True)
class ConversationTurn:
    """A single completed user-assistant exchange.

    Both fields are plaintext; secrets MUST NOT be stored here (the
    upstream SSE pipeline already redacts sensitive payloads).
    """

    user: str
    assistant: str

    def format_for_prompt(self, max_field_chars: int | None = None) -> str:
        """Render this turn as a compact ``User: … / Assistant: …`` block.

        Deterministic so the LLM sees the same framing every time —
        prompt-injection resistance depends on the structure being
        predictable from the agent's perspective. ``max_field_chars``
        truncates each field so one giant reply cannot dominate the prompt.
        """
        user = self.user if max_field_chars is None else _truncate(self.user, max_field_chars)
        assistant = self.assistant if max_field_chars is None else _truncate(self.assistant, max_field_chars)
        return f"User: {user}\nAssistant: {assistant}"


class ConversationBuffer:
    """In-memory per-user per-session ring buffer with cross-key LRU eviction.

    The buffer is partitioned by the composite key ``(user_id, session_id)``
    rather than by ``session_id`` alone. This prevents a class of
    cross-tenant data-leak attacks where one user's frontend-generated
    ``session_id`` (which routinely appears in logs, observability traces,
    request headers, and operational hooks) could be POSTed by another
    tenant to extract the original user's conversation history into their
    own prompt.
    """

    def __init__(self) -> None:
        # The tuple key is the security boundary — keying by session_id alone
        # reintroduces the cross-tenant leak.
        self._sessions: OrderedDict[tuple[str, str], deque[ConversationTurn]] = OrderedDict()
        self._lock = asyncio.Lock()

    def push(self, user_id: str, session_id: str, turn: ConversationTurn) -> None:
        """Append ``turn`` to ``(user_id, session_id)``'s buffer.

        - Creates a new bounded deque if the (user, session) pair is unknown.
        - Refreshes the pair's LRU slot.
        - Evicts the oldest pair if we exceed ``MAX_SESSIONS``.
        """
        key = (user_id, session_id)
        buf = self._sessions.get(key)
        if buf is None:
            buf = deque(maxlen=MAX_TURNS_PER_SESSION)
            self._sessions[key] = buf
        buf.append(turn)
        self._sessions.move_to_end(key)
        while len(self._sessions) > MAX_SESSIONS:
            self._sessions.popitem(last=False)

    async def push_async(self, user_id: str, session_id: str, turn: ConversationTurn) -> None:
        """Lock-protected variant for concurrent callers (asyncio.gather).

        ``push`` itself uses bounded deque + OrderedDict which are CPython
        thread-safe for single ops, but composite operations (move_to_end
        after append) need the lock to stay atomic from the caller's POV.
        """
        async with self._lock:
            self.push(user_id, session_id, turn)

    def get_recent(self, user_id: str, session_id: str, limit: int | None = None) -> list[ConversationTurn]:
        """Return up to ``limit`` most recent turns for ``(user_id, session_id)``, oldest-first.

        Unknown ``(user_id, session_id)`` → empty list. ``limit=None`` returns
        the entire buffer for that pair; ``limit <= 0`` returns none (zero
        means "history disabled", and ``turns[-0:]`` would leak the whole
        buffer). A different ``user_id`` reusing the same ``session_id``
        MUST receive an empty list — that is the cross-tenant isolation
        contract this method guarantees.
        """
        buf = self._sessions.get((user_id, session_id))
        if buf is None:
            return []
        turns = list(buf)
        if limit is None:
            return turns
        if limit <= 0:
            return []
        return turns[-limit:]

    def clear(self, user_id: str, session_id: str) -> None:
        """Drop just the ``(user_id, session_id)`` pair. Idempotent."""
        self._sessions.pop((user_id, session_id), None)


# Intentionally NOT in the langflow service registry: no async startup,
# no shutdown resources, no user-controlled configuration.
_singleton: ConversationBuffer | None = None


def get_conversation_buffer() -> ConversationBuffer:
    """Return the process-wide singleton, lazily instantiated."""
    global _singleton  # noqa: PLW0603 — intentional process-wide buffer accessor
    if _singleton is None:
        _singleton = ConversationBuffer()
    return _singleton
