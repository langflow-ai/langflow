import pytest

from langflow.memory import add_messages, add_messagetables, delete_messages, get_messages, store_message
from langflow.schema.message import Message

# Assuming you have these imports available
from langflow.services.database.models.message import MessageCreate, MessageRead
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope
from langflow.services.tracing.utils import convert_to_langchain_type


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


@pytest.mark.usefixtures("client")
def test_get_messages():
    add_messages(
        [
            Message(text="Test message 1", sender="User", sender_name="User", session_id="session_id2"),
            Message(text="Test message 2", sender="User", sender_name="User", session_id="session_id2"),
        ]
    )
    messages = get_messages(sender="User", session_id="session_id2", limit=2)
    assert len(messages) == 2
    assert messages[0].text == "Test message 1"
    assert messages[1].text == "Test message 2"


@pytest.mark.usefixtures("client")
def test_add_messages():
    message = Message(text="New Test message", sender="User", sender_name="User", session_id="new_session_id")
    messages = add_messages(message)
    assert len(messages) == 1
    assert messages[0].text == "New Test message"


@pytest.mark.usefixtures("client")
def test_add_messagetables(session):
    messages = [MessageTable(text="New Test message", sender="User", sender_name="User", session_id="new_session_id")]
    added_messages = add_messagetables(messages, session)
    assert len(added_messages) == 1
    assert added_messages[0].text == "New Test message"


@pytest.mark.usefixtures("client")
def test_delete_messages(session):
    session_id = "session_id2"
    delete_messages(session_id)
    messages = session.query(MessageTable).filter(MessageTable.session_id == session_id).all()
    assert len(messages) == 0


@pytest.mark.usefixtures("client")
def test_store_message():
    message = Message(text="Stored message", sender="User", sender_name="User", session_id="stored_session_id")
    stored_messages = store_message(message)
    assert len(stored_messages) == 1
    assert stored_messages[0].text == "Stored message"


@pytest.mark.parametrize("method_name", ["message", "convert_to_langchain_type"])
def test_convert_to_langchain(method_name):
    def convert(value):
        if method_name == "message":
            return value.to_lc_message()
        elif method_name == "convert_to_langchain_type":
            return convert_to_langchain_type(value)
        else:
            raise ValueError(f"Invalid method: {method_name}")

    lc_message = convert(Message(text="Test message 1", sender="User", sender_name="User", session_id="session_id2"))
    assert lc_message.content == "Test message 1"
    assert lc_message.type == "human"

    lc_message = convert(Message(text="Test message 2", sender="AI", session_id="session_id2"))
    assert lc_message.content == "Test message 2"
    assert lc_message.type == "ai"

    iterator = iter(["stream", "message"])
    lc_message = convert(Message(text=iterator, sender="AI", session_id="session_id2"))
    assert lc_message.content == ""
    assert lc_message.type == "ai"
    assert len(list(iterator)) == 2
