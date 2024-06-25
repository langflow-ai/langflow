import pytest

from langflow.memory import add_messages, add_messagetables, delete_messages, get_messages, store_message
from langflow.schema.message import Message

# Assuming you have these imports available
from langflow.services.database.models.message import MessageCreate, MessageRead
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope


@pytest.fixture()
def created_message():
    with session_scope() as session:
        message = MessageCreate(text="Test message", sender="User", sender_name="User", session_id="session_id")
        messagetable = MessageTable.model_validate(message, from_attributes=True)
        messagetables = add_messagetables([messagetable], session)
        message_read = MessageRead.model_validate(messagetables[0], from_attributes=True)
        return message_read


@pytest.fixture()
def created_messages(session):
    with session_scope() as session:
        messages = [
            MessageCreate(text="Test message 1", sender="User", sender_name="User", session_id="session_id2"),
            MessageCreate(text="Test message 2", sender="User", sender_name="User", session_id="session_id2"),
            MessageCreate(text="Test message 3", sender="User", sender_name="User", session_id="session_id2"),
        ]
        messagetables = [MessageTable.model_validate(message, from_attributes=True) for message in messages]
        messagetables = add_messagetables(messagetables, session)
        messages_read = [
            MessageRead.model_validate(messagetable, from_attributes=True) for messagetable in messagetables
        ]
        return messages_read


def test_get_messages(session):
    add_messages(Message(text="Test message 1", sender="User", sender_name="User", session_id="session_id2"))
    add_messages(Message(text="Test message 2", sender="User", sender_name="User", session_id="session_id2"))
    messages = get_messages(sender="User", session_id="session_id2", limit=2)
    assert len(messages) == 2
    assert messages[0].text == "Test message 1"
    assert messages[1].text == "Test message 2"


def test_add_messages(session):
    message = Message(text="New Test message", sender="User", sender_name="User", session_id="new_session_id")
    messages = add_messages(message)
    assert len(messages) == 1
    assert messages[0].text == "New Test message"


def test_add_messagetables(session):
    messages = [MessageTable(text="New Test message", sender="User", sender_name="User", session_id="new_session_id")]
    added_messages = add_messagetables(messages, session)
    assert len(added_messages) == 1
    assert added_messages[0].text == "New Test message"


def test_delete_messages(session):
    session_id = "session_id2"
    delete_messages(session_id)
    messages = session.query(MessageTable).filter(MessageTable.session_id == session_id).all()
    assert len(messages) == 0


def test_store_message(session):
    message = Message(text="Stored message", sender="User", sender_name="User", session_id="stored_session_id")
    stored_messages = store_message(message)
    assert len(stored_messages) == 1
    assert stored_messages[0].text == "Stored message"
