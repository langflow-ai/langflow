"""Regression tests for cross-user chat-history disclosure (CWE-200).

The Memory component / run path filtered messages on ``session_id`` alone, so an authenticated
attacker who reused a victim's ``session_id`` could read the victim's chat history. Messages are
now stamped with the executing user's id (``MessageTable.user_id``) on write, and ``aget_messages``
filters on it when a user scope is supplied — while omitting the scope preserves legacy behavior.
"""

from uuid import uuid4

import pytest
from langflow.memory import aadd_messages, aget_messages
from langflow.schema.message import Message
from langflow.services.database.models.message.model import MessageTable


async def _store(session_id: str, user_id, text: str) -> None:
    msg = Message(text=text, sender="User", sender_name="User", session_id=session_id)
    await aadd_messages([msg], user_id=user_id)


async def test_aget_messages_scopes_by_user_id(client):  # noqa: ARG001
    """Two users sharing a session_id see only their own messages when scoped by user_id."""
    user_a, user_b = uuid4(), uuid4()
    session_id = "shared-session-le1675"
    await _store(session_id, user_a, "secret from A")
    await _store(session_id, user_b, "secret from B")

    a_msgs = await aget_messages(session_id=session_id, user_id=user_a)
    b_msgs = await aget_messages(session_id=session_id, user_id=user_b)
    unscoped = await aget_messages(session_id=session_id)

    assert [m.text for m in a_msgs] == ["secret from A"]
    assert [m.text for m in b_msgs] == ["secret from B"]
    # No user_id => legacy unscoped behavior (both users' messages), preserving backward compat.
    assert len(unscoped) == 2


async def test_aget_messages_scopes_by_string_user_id(client):  # noqa: ARG001
    """Retrieval must accept a *string* user_id scope, as runtime callers supply.

    ``_safe_graph_user_id`` returns ``graph.user_id`` unchanged (a ``str``), so ``aget_messages``
    receives a string scope. ``MessageTable.user_id`` is UUID-typed; on SQLite the ``Uuid`` bind
    processor calls ``value.hex`` and raises ``'str' object has no attribute 'hex'`` for a raw
    string. The query path must coerce the scope to ``UUID`` before building the predicate.
    """
    user_a, user_b = uuid4(), uuid4()
    session_id = "shared-session-le1675-str"
    await _store(session_id, user_a, "secret from A")
    await _store(session_id, user_b, "secret from B")

    # Pass the scope as a string, mirroring _safe_graph_user_id(graph.user_id).
    a_msgs = await aget_messages(session_id=session_id, user_id=str(user_a))
    b_msgs = await aget_messages(session_id=session_id, user_id=str(user_b))

    assert [m.text for m in a_msgs] == ["secret from A"]
    assert [m.text for m in b_msgs] == ["secret from B"]


async def test_from_message_stamps_user_id():
    """from_message stamps and coerces user_id; an invalid string is rejected."""
    user_a = uuid4()
    msg = Message(text="hi", sender="User", sender_name="User", session_id="s")
    assert MessageTable.from_message(msg, user_id=user_a).user_id == user_a
    assert MessageTable.from_message(msg, user_id=str(user_a)).user_id == user_a
    with pytest.raises(ValueError, match="not a valid UUID"):
        MessageTable.from_message(msg, user_id="not-a-uuid")
