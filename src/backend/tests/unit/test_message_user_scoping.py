"""Regression tests for cross-user chat-history disclosure."""

from uuid import uuid4

import pytest
from langflow.memory import aadd_messages, aget_messages
from langflow.schema.message import Message
from langflow.services.database.models.message.model import MessageTable


async def _store(session_id: str, user_id, text: str) -> None:
    message = Message(text=text, sender="User", sender_name="User", session_id=session_id)
    await aadd_messages([message], user_id=user_id)


async def test_aget_messages_scopes_shared_session_by_user(client):  # noqa: ARG001
    user_a, user_b = uuid4(), uuid4()
    session_id = "shared-session-message-owner"
    await _store(session_id, user_a, "secret from A")
    await _store(session_id, user_b, "secret from B")

    assert [message.text for message in await aget_messages(session_id=session_id, user_id=user_a)] == ["secret from A"]
    assert [message.text for message in await aget_messages(session_id=session_id, user_id=str(user_b))] == [
        "secret from B"
    ]
    assert len(await aget_messages(session_id=session_id)) == 2


async def test_from_message_stamps_and_validates_user_id():
    user_id = uuid4()
    message = Message(text="hi", sender="User", sender_name="User", session_id="s")

    assert MessageTable.from_message(message, user_id=user_id).user_id == user_id
    assert MessageTable.from_message(message, user_id=str(user_id)).user_id == user_id
    with pytest.raises(ValueError, match="not a valid UUID"):
        MessageTable.from_message(message, user_id="not-a-uuid")
