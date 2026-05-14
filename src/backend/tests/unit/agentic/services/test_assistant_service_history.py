"""Integration tests for conversation-history injection in assistant_service.

These tests pin two behaviors:
    1. When a session has prior turns in the buffer, the agent's input
       gets prefixed with a ``[Conversation history]`` block (oldest-first).
    2. After a successful run, the (user, assistant) turn is appended
       to the buffer for that session.

Wiring is exercised by patching the buffer module's singleton accessor —
we don't need to drive the full SSE flow.
"""

from __future__ import annotations

import pytest
from langflow.agentic.services.conversation_buffer import (
    ConversationBuffer,
    ConversationTurn,
)


@pytest.fixture
def fresh_buffer(monkeypatch):
    """Swap the module-level singleton with a fresh, empty buffer."""
    import langflow.agentic.services.conversation_buffer as module

    buf = ConversationBuffer()
    monkeypatch.setattr(module, "_singleton", buf)
    return buf


def test_inject_history_should_prefix_input_with_oldest_first_turns(fresh_buffer):
    """The helper used by assistant_service injects prior turns before the new input."""
    from langflow.agentic.services.assistant_service import inject_conversation_history

    fresh_buffer.push(
        "alice",
        "s1",
        ConversationTurn(user="how do I add Memory?", assistant="Use the Memory component."),
    )
    fresh_buffer.push(
        "alice",
        "s1",
        ConversationTurn(user="and a tool?", assistant="Add WebCrawler."),
    )

    wrapped = inject_conversation_history(
        user_id="alice",
        session_id="s1",
        input_value="now build the flow",
    )

    # Oldest turn first; newest just before the user's current input.
    idx_old = wrapped.find("how do I add Memory?")
    idx_new = wrapped.find("and a tool?")
    idx_user = wrapped.find("now build the flow")
    assert idx_old < idx_new < idx_user, "Turns must be oldest-first then the live input"
    # Loose framing assertion — must distinguish history from new input.
    assert "Conversation history" in wrapped


def test_inject_history_should_return_unchanged_input_when_no_session_history(
    fresh_buffer,  # noqa: ARG001 — fixture patches the singleton to a fresh buffer
):
    from langflow.agentic.services.assistant_service import inject_conversation_history

    wrapped = inject_conversation_history(user_id="alice", session_id="never-pushed", input_value="hi")

    assert wrapped == "hi"


def test_inject_history_should_return_unchanged_input_when_session_id_none(
    fresh_buffer,  # noqa: ARG001 — fixture patches the singleton to a fresh buffer
):
    # An anonymous request (no session_id) carries no history — must
    # noop rather than blow up.
    from langflow.agentic.services.assistant_service import inject_conversation_history

    wrapped = inject_conversation_history(user_id="alice", session_id=None, input_value="hi")

    assert wrapped == "hi"


def test_inject_history_should_return_unchanged_input_when_user_id_none(
    fresh_buffer,  # noqa: ARG001 — fixture patches the singleton to a fresh buffer
):
    # Anonymous tenant (no auth context). Refuse to read shared state.
    from langflow.agentic.services.assistant_service import inject_conversation_history

    wrapped = inject_conversation_history(user_id=None, session_id="s1", input_value="hi")

    assert wrapped == "hi"


def test_record_turn_should_push_completed_exchange_to_buffer(fresh_buffer):
    from langflow.agentic.services.assistant_service import record_conversation_turn

    record_conversation_turn(
        user_id="alice",
        session_id="s1",
        user_input="build a flow",
        assistant_response="Built the flow.",
    )

    recent = fresh_buffer.get_recent("alice", "s1")
    assert len(recent) == 1
    assert recent[0].user == "build a flow"
    assert recent[0].assistant == "Built the flow."


def test_record_turn_should_skip_when_session_id_none(fresh_buffer):
    from langflow.agentic.services.assistant_service import record_conversation_turn

    record_conversation_turn(
        user_id="alice",
        session_id=None,
        user_input="anonymous",
        assistant_response="reply",
    )

    # Nothing pushed — anonymous requests don't share history.
    assert fresh_buffer.get_recent("alice", "anonymous") == []


def test_record_turn_should_skip_when_user_id_none(fresh_buffer):
    from langflow.agentic.services.assistant_service import record_conversation_turn

    record_conversation_turn(
        user_id=None,
        session_id="s1",
        user_input="no-tenant",
        assistant_response="reply",
    )

    # Nothing pushed — anonymous tenant cannot share history.
    assert fresh_buffer.get_recent("", "s1") == []


def test_record_turn_should_skip_empty_responses(fresh_buffer):
    # A cancelled or errored turn ends up with an empty assistant_response.
    # Storing it would just pollute the next turn's context.
    from langflow.agentic.services.assistant_service import record_conversation_turn

    record_conversation_turn(
        user_id="alice",
        session_id="s1",
        user_input="will be cancelled",
        assistant_response="",
    )

    assert fresh_buffer.get_recent("alice", "s1") == []


class TestCrossTenantIsolation:
    """SECURITY regression — buffer MUST partition by user_id, not just session_id.

    Bug shape: ``session_id`` is a frontend-generated UUID. Anyone who learns
    Alice's session_id (via Langfuse/log exfil, X-Session-Id header echoing,
    operational hooks, or a misconfigured observability sink) can POST it as
    their own session_id and read Alice's conversation history in their prompt.

    Fix shape: key the buffer by the composite ``(user_id, session_id)``.
    """

    def test_should_not_leak_history_to_a_different_user_with_the_same_session_id(
        self,
        fresh_buffer,  # noqa: ARG002 — fixture patches the singleton to a fresh buffer
    ):
        from langflow.agentic.services.assistant_service import (
            inject_conversation_history,
            record_conversation_turn,
        )

        # Arrange — Alice records a turn carrying private content under sid "s1".
        record_conversation_turn(
            user_id="alice",
            session_id="s1",
            user_input="my private credential is hunter2",
            assistant_response="acknowledged",
        )

        # Act — Bob (different tenant) POSTs the SAME session_id.
        wrapped = inject_conversation_history(
            user_id="bob",
            session_id="s1",
            input_value="what was just said?",
        )

        # Assert — Bob's prompt MUST NOT contain any of Alice's content.
        assert "hunter2" not in wrapped, (
            "Cross-tenant data leak: Bob received Alice's conversation history "
            "by reusing her session_id. ConversationBuffer must be partitioned "
            "by (user_id, session_id), not by session_id alone."
        )
        assert "my private credential" not in wrapped
        assert "Conversation history" not in wrapped, (
            "Bob's prompt should have NO history block at all — his (user_id, sid) "
            "key is fresh, so the buffer must report 0 turns."
        )

    def test_should_still_return_owner_history_when_same_user_reuses_session_id(
        self,
        fresh_buffer,  # noqa: ARG002 — fixture patches the singleton to a fresh buffer
    ):
        # Sanity twin: the same user (matching user_id + session_id) STILL sees
        # their own history. Proves the fix doesn't over-isolate.
        from langflow.agentic.services.assistant_service import (
            inject_conversation_history,
            record_conversation_turn,
        )

        record_conversation_turn(
            user_id="alice",
            session_id="s1",
            user_input="how do I add Memory?",
            assistant_response="Use the Memory component.",
        )

        wrapped = inject_conversation_history(
            user_id="alice",
            session_id="s1",
            input_value="and a tool?",
        )

        assert "how do I add Memory?" in wrapped
        assert "Conversation history" in wrapped
