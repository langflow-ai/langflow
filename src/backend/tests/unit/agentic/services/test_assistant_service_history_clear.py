"""Tests for the session-clear API endpoint hook.

When the user starts a new session in the frontend, the backend needs a
way to drop the prior session's buffer entry. This is exposed via a
small helper in ``assistant_service`` so the router can call it without
importing the buffer module directly.
"""

from __future__ import annotations

import pytest
from langflow.agentic.services.conversation_buffer import (
    ConversationBuffer,
    ConversationTurn,
)


@pytest.fixture
def fresh_buffer(monkeypatch):
    import langflow.agentic.services.conversation_buffer as module

    buf = ConversationBuffer()
    monkeypatch.setattr(module, "_singleton", buf)
    return buf


def test_clear_session_history_should_drop_the_named_session(fresh_buffer):
    from langflow.agentic.services.assistant_service import clear_session_history

    fresh_buffer.push("alice", "s1", ConversationTurn(user="x", assistant="y"))
    fresh_buffer.push("alice", "s2", ConversationTurn(user="a", assistant="b"))

    clear_session_history("alice", "s1")

    assert fresh_buffer.get_recent("alice", "s1") == []
    # Sibling session is untouched.
    assert len(fresh_buffer.get_recent("alice", "s2")) == 1


def test_clear_session_history_should_skip_when_session_id_none(fresh_buffer):
    from langflow.agentic.services.assistant_service import clear_session_history

    fresh_buffer.push("alice", "s1", ConversationTurn(user="x", assistant="y"))
    # Should not raise and should not touch any session.
    clear_session_history("alice", None)
    assert len(fresh_buffer.get_recent("alice", "s1")) == 1


def test_clear_session_history_should_skip_when_user_id_none(fresh_buffer):
    from langflow.agentic.services.assistant_service import clear_session_history

    fresh_buffer.push("alice", "s1", ConversationTurn(user="x", assistant="y"))
    # Should not raise and should not touch any session.
    clear_session_history(None, "s1")
    assert len(fresh_buffer.get_recent("alice", "s1")) == 1


def test_clear_session_history_should_not_drop_other_users_session_with_same_id(fresh_buffer):
    """SECURITY twin: ``clear`` is also keyed by ``(user_id, session_id)``.

    One tenant cannot wipe another's buffer by guessing/replaying a session_id.
    """
    from langflow.agentic.services.assistant_service import clear_session_history

    fresh_buffer.push("alice", "s1", ConversationTurn(user="x", assistant="y"))

    # Bob attempts to clear Alice's session by posting the same session_id.
    clear_session_history("bob", "s1")

    # Alice's history must survive.
    assert len(fresh_buffer.get_recent("alice", "s1")) == 1


def test_clear_session_history_should_be_idempotent_for_unknown_session(
    fresh_buffer,  # noqa: ARG001 — fixture patches the singleton to a fresh buffer
):
    from langflow.agentic.services.assistant_service import clear_session_history

    clear_session_history("alice", "never-pushed")  # no error
