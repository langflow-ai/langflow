"""Story 0.2 — Context Manager.

`build_messages` is a pure function, so these tests need no DB or fixtures: they
construct in-memory `Message` rows and assert the exact `messages` array shape
for known inputs.
"""

from uuid import uuid4

import pytest
from langflow.lothal.context import build_messages
from langflow.services.database.models.lothal_project.model import Message


def _message(role: str, content: str) -> Message:
    """An unflushed Message; only `role` and `content` matter to build_messages."""
    return Message(project_id=uuid4(), role=role, content=content, phase="CLARIFICATION")


def test_empty_history_is_system_then_user():
    result = build_messages("You are helpful.", [], "Build me a todo app.")

    assert result == [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Build me a todo app."},
    ]


def test_full_structure_with_history_in_order():
    history = [
        _message("USER", "Build me a todo app."),
        _message("ASSISTANT", "Who are the users?"),
        _message("USER", "Just me."),
        _message("ASSISTANT", "Any deadlines?"),
    ]

    result = build_messages("SYS", history, "No deadlines.")

    assert result == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "Build me a todo app."},
        {"role": "assistant", "content": "Who are the users?"},
        {"role": "user", "content": "Just me."},
        {"role": "assistant", "content": "Any deadlines?"},
        {"role": "user", "content": "No deadlines."},
    ]


def test_does_not_mutate_inputs():
    history = [_message("USER", "hi")]

    build_messages("SYS", history, "again")

    assert len(history) == 1
    assert history[0].role == "USER"
    assert history[0].content == "hi"


def test_unknown_role_raises():
    history = [_message("SYSTEM", "smuggled system turn")]

    with pytest.raises(ValueError, match="Unsupported message role"):
        build_messages("SYS", history, "go")
