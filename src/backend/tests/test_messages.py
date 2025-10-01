from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from langflow.memory import (
    aadd_messages,
    aadd_messagetables,
    add_messages,
    adelete_messages,
    aget_messages,
    astore_message,
    aupdate_messages,
    delete_messages,
    get_messages,
)
from langflow.schema.content_block import ContentBlock
from langflow.schema.content_types import TextContent, ToolContent
from langflow.schema.message import Message
from langflow.schema.properties import Properties, Source

# Assuming you have these imports available
from langflow.services.database.models.message import MessageCreate, MessageRead
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope
from langflow.services.tracing.utils import convert_to_langchain_type


@pytest.fixture
async def created_message():
    async with session_scope() as session:
        message = MessageCreate(text="Test message", sender="User", sender_name="User", session_id="session_id")
        messagetable = MessageTable.model_validate(message, from_attributes=True)
        messagetables = await aadd_messagetables([messagetable], session)
        return MessageRead.model_validate(messagetables[0], from_attributes=True)


@pytest.fixture
async def created_messages(async_session):  # noqa: ARG001
    async with session_scope() as _session:
        messages = [
            MessageCreate(text="Test message 1", sender="User", sender_name="User", session_id="session_id2"),
            MessageCreate(text="Test message 2", sender="User", sender_name="User", session_id="session_id2"),
            MessageCreate(text="Test message 3", sender="User", sender_name="User", session_id="session_id2"),
        ]
        messagetables = [MessageTable.model_validate(message, from_attributes=True) for message in messages]
        messagetables = await aadd_messagetables(messagetables, _session)
        return [MessageRead.model_validate(messagetable, from_attributes=True) for messagetable in messagetables]


@pytest.mark.usefixtures("client")
def test_get_messages():
    add_messages(
        [
            Message(text="Test message 1", sender="User", sender_name="User", session_id="session_id2"),
            Message(text="Test message 2", sender="User", sender_name="User", session_id="session_id2"),
        ]
    )
    limit = 2
    messages = get_messages(sender="User", session_id="session_id2", limit=limit)
    assert len(messages) == limit
    assert messages[0].text == "Test message 1"
    assert messages[1].text == "Test message 2"


@pytest.mark.usefixtures("client")
async def test_aget_messages():
    await aadd_messages(
        [
            Message(text="Test message 1", sender="User", sender_name="User", session_id="session_id2"),
            Message(text="Test message 2", sender="User", sender_name="User", session_id="session_id2"),
        ]
    )
    limit = 2
    messages = await aget_messages(sender="User", session_id="session_id2", limit=limit)
    assert len(messages) == limit
    assert messages[0].text == "Test message 1"
    assert messages[1].text == "Test message 2"


@pytest.mark.usefixtures("client")
def test_add_messages():
    message = Message(text="New Test message", sender="User", sender_name="User", session_id="new_session_id")
    messages = add_messages(message)
    assert len(messages) == 1
    assert messages[0].text == "New Test message"


@pytest.mark.usefixtures("client")
async def test_aadd_messages():
    message = Message(text="New Test message", sender="User", sender_name="User", session_id="new_session_id")
    messages = await aadd_messages(message)
    assert len(messages) == 1
    assert messages[0].text == "New Test message"


@pytest.mark.usefixtures("client")
async def test_aadd_messagetables(async_session):
    messages = [MessageTable(text="New Test message", sender="User", sender_name="User", session_id="new_session_id")]
    added_messages = await aadd_messagetables(messages, async_session)
    assert len(added_messages) == 1
    assert added_messages[0].text == "New Test message"


@pytest.mark.usefixtures("client")
def test_delete_messages():
    session_id = "new_session_id"
    message = Message(text="New Test message", sender="User", sender_name="User", session_id=session_id)
    add_messages([message])
    messages = get_messages(sender="User", session_id=session_id)
    assert len(messages) == 1
    delete_messages(session_id)
    messages = get_messages(sender="User", session_id=session_id)
    assert len(messages) == 0


@pytest.mark.usefixtures("client")
async def test_adelete_messages():
    session_id = "new_session_id"
    message = Message(text="New Test message", sender="User", sender_name="User", session_id=session_id)
    await aadd_messages([message])
    messages = await aget_messages(sender="User", session_id=session_id)
    assert len(messages) == 1
    await adelete_messages(session_id)
    messages = await aget_messages(sender="User", session_id=session_id)
    assert len(messages) == 0


@pytest.mark.usefixtures("client")
async def test_store_message():
    session_id = "stored_session_id"
    message = Message(text="Stored message", sender="User", sender_name="User", session_id=session_id)
    await astore_message(message)
    stored_messages = await aget_messages(sender="User", session_id=session_id)
    assert len(stored_messages) == 1
    assert stored_messages[0].text == "Stored message"


@pytest.mark.usefixtures("client")
async def test_astore_message():
    session_id = "stored_session_id"
    message = Message(text="Stored message", sender="User", sender_name="User", session_id=session_id)
    await astore_message(message)
    stored_messages = await aget_messages(sender="User", session_id=session_id)
    assert len(stored_messages) == 1
    assert stored_messages[0].text == "Stored message"


@pytest.mark.parametrize("method_name", ["message", "convert_to_langchain_type"])
def test_convert_to_langchain(method_name):
    def convert(value):
        if method_name == "message":
            return value.to_lc_message()
        if method_name == "convert_to_langchain_type":
            return convert_to_langchain_type(value)
        msg = f"Invalid method: {method_name}"
        raise ValueError(msg)

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
    expected_len = 2
    assert len(list(iterator)) == expected_len


@pytest.mark.usefixtures("client")
async def test_aupdate_single_message(created_message):
    # Modify the message
    created_message.text = "Updated message"
    updated = await aupdate_messages(created_message)

    assert len(updated) == 1
    assert updated[0].text == "Updated message"
    assert updated[0].id == created_message.id


@pytest.mark.usefixtures("client")
async def test_aupdate_multiple_messages(created_messages):
    # Modify the messages
    for i, message in enumerate(created_messages):
        message.text = f"Updated message {i}"

    updated = await aupdate_messages(created_messages)

    assert len(updated) == len(created_messages)
    for i, message in enumerate(updated):
        assert message.text == f"Updated message {i}"
        assert message.id == created_messages[i].id


@pytest.mark.usefixtures("client")
async def test_aupdate_nonexistent_message_generates_a_new_message():
    # Create a message with a non-existent UUID
    nonexistent_uuid = uuid4()
    message = MessageRead(
        id=nonexistent_uuid,  # Generate a random UUID that won't exist in the database
        text="Test message",
        sender="User",
        sender_name="User",
        session_id="session_id",
        flow_id=uuid4(),
    )
    with pytest.raises(ValueError, match=f"Message with id {nonexistent_uuid} not found"):
        await aupdate_messages(message)


@pytest.mark.usefixtures("client")
async def test_aupdate_mixed_messages(created_messages):
    # Create a mix of existing and non-existing messages
    nonexistent_uuid = uuid4()
    nonexistent_message = MessageRead(
        id=nonexistent_uuid,  # Generate a random UUID that won't exist in the database
        text="Test message",
        sender="User",
        sender_name="User",
        session_id="session_id",
        flow_id=uuid4(),
    )

    messages_to_update = [*created_messages[:1], nonexistent_message]
    created_messages[0].text = "Updated existing message"

    with pytest.raises(ValueError, match=f"Message with id {nonexistent_uuid} not found"):
        await aupdate_messages(messages_to_update)

    # Update just the existing message
    updated = await aupdate_messages(created_messages[:1])

    assert len(updated) == 1
    assert updated[0].text == "Updated existing message"
    assert updated[0].id == created_messages[0].id
    assert isinstance(updated[0].id, UUID)  # Verify ID is UUID type


@pytest.mark.usefixtures("client")
async def test_aupdate_message_with_timestamp(created_message):
    # Set a specific timestamp
    new_timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    created_message.timestamp = new_timestamp
    created_message.text = "Updated message with timestamp"

    updated = await aupdate_messages(created_message)

    assert len(updated) == 1
    assert updated[0].text == "Updated message with timestamp"

    # Compare timestamps without timezone info since DB doesn't preserve it
    assert updated[0].timestamp.replace(tzinfo=None) == new_timestamp.replace(tzinfo=None)
    assert updated[0].id == created_message.id


@pytest.mark.usefixtures("client")
async def test_aupdate_multiple_messages_with_timestamps(created_messages):
    # Modify messages with different timestamps
    for i, message in enumerate(created_messages):
        message.text = f"Updated message {i}"
        message.timestamp = datetime(2024, 1, 1, i, 0, 0, tzinfo=timezone.utc)

    updated = await aupdate_messages(created_messages)

    assert len(updated) == len(created_messages)
    for i, message in enumerate(updated):
        assert message.text == f"Updated message {i}"
        # Compare timestamps without timezone info
        expected_timestamp = datetime(2024, 1, 1, i, 0, 0, tzinfo=timezone.utc)
        assert message.timestamp.replace(tzinfo=None) == expected_timestamp.replace(tzinfo=None)
        assert message.id == created_messages[i].id


@pytest.mark.usefixtures("client")
async def test_aupdate_message_with_content_blocks(created_message):
    # Create a content block using proper models
    text_content = TextContent(
        type="text", text="Test content", duration=5, header={"title": "Test Header", "icon": "TestIcon"}
    )

    tool_content = ToolContent(type="tool_use", name="test_tool", tool_input={"param": "value"}, duration=10)

    content_block = ContentBlock(title="Test Block", contents=[text_content, tool_content], allow_markdown=True)

    created_message.content_blocks = [content_block]
    created_message.text = "Message with content blocks"

    updated = await aupdate_messages(created_message)

    assert len(updated) == 1
    assert updated[0].text == "Message with content blocks"
    assert len(updated[0].content_blocks) == 1

    # Verify the content block structure
    updated_block = updated[0].content_blocks[0]
    assert updated_block.title == "Test Block"
    expected_len = 2
    assert len(updated_block.contents) == expected_len

    # Verify text content
    text_content = updated_block.contents[0]
    assert text_content.type == "text"
    assert text_content.text == "Test content"
    duration = 5
    assert text_content.duration == duration
    assert text_content.header["title"] == "Test Header"

    # Verify tool content
    tool_content = updated_block.contents[1]
    assert tool_content.type == "tool_use"
    assert tool_content.name == "test_tool"
    assert tool_content.tool_input == {"param": "value"}
    duration = 10
    assert tool_content.duration == duration


@pytest.mark.usefixtures("client")
async def test_aupdate_message_with_nested_properties(created_message):
    # Create a text content with nested properties
    text_content = TextContent(
        type="text", text="Test content", header={"title": "Test Header", "icon": "TestIcon"}, duration=15
    )

    content_block = ContentBlock(
        title="Test Properties",
        contents=[text_content],
        allow_markdown=True,
        media_url=["http://example.com/image.jpg"],
    )

    # Set properties according to the Properties model structure
    created_message.properties = Properties(
        text_color="blue",
        background_color="white",
        edited=False,
        source=Source(id="test_id", display_name="Test Source", source="test"),
        icon="TestIcon",
        allow_markdown=True,
        state="complete",
        targets=[],
    )
    created_message.text = "Message with nested properties"
    created_message.content_blocks = [content_block]

    updated = await aupdate_messages(created_message)

    assert len(updated) == 1
    assert updated[0].text == "Message with nested properties"

    # Verify the properties were properly serialized and stored
    assert updated[0].properties.text_color == "blue"
    assert updated[0].properties.background_color == "white"
    assert updated[0].properties.edited is False
    assert updated[0].properties.source.id == "test_id"
    assert updated[0].properties.source.display_name == "Test Source"
    assert updated[0].properties.source.source == "test"
    assert updated[0].properties.icon == "TestIcon"
    assert updated[0].properties.allow_markdown is True
    assert updated[0].properties.state == "complete"
    assert updated[0].properties.targets == []
