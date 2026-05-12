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
        "s1",
        ConversationTurn(user="how do I add Memory?", assistant="Use the Memory component."),
    )
    fresh_buffer.push(
        "s1",
        ConversationTurn(user="and a tool?", assistant="Add WebCrawler."),
    )

    wrapped = inject_conversation_history(
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

    wrapped = inject_conversation_history(session_id="never-pushed", input_value="hi")

    assert wrapped == "hi"


def test_inject_history_should_return_unchanged_input_when_session_id_none(
    fresh_buffer,  # noqa: ARG001 — fixture patches the singleton to a fresh buffer
):
    # An anonymous request (no session_id) carries no history — must
    # noop rather than blow up.
    from langflow.agentic.services.assistant_service import inject_conversation_history

    wrapped = inject_conversation_history(session_id=None, input_value="hi")

    assert wrapped == "hi"


def test_record_turn_should_push_completed_exchange_to_buffer(fresh_buffer):
    from langflow.agentic.services.assistant_service import record_conversation_turn

    record_conversation_turn(
        session_id="s1",
        user_input="build a flow",
        assistant_response="Built the flow.",
    )

    recent = fresh_buffer.get_recent("s1")
    assert len(recent) == 1
    assert recent[0].user == "build a flow"
    assert recent[0].assistant == "Built the flow."


def test_record_turn_should_skip_when_session_id_none(fresh_buffer):
    from langflow.agentic.services.assistant_service import record_conversation_turn

    record_conversation_turn(
        session_id=None,
        user_input="anonymous",
        assistant_response="reply",
    )

    # Nothing pushed — anonymous requests don't share history.
    assert fresh_buffer.get_recent("anonymous") == []


def test_record_turn_should_skip_empty_responses(fresh_buffer):
    # A cancelled or errored turn ends up with an empty assistant_response.
    # Storing it would just pollute the next turn's context.
    from langflow.agentic.services.assistant_service import record_conversation_turn

    record_conversation_turn(
        session_id="s1",
        user_input="will be cancelled",
        assistant_response="",
    )

    assert fresh_buffer.get_recent("s1") == []
