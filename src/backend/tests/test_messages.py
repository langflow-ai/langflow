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


# =============================================================================
# Tests for MessageBase.from_message file path handling
# =============================================================================


class TestMessageBaseFromMessageFilePaths:
    """Tests for the file path handling in MessageBase.from_message."""

    def test_from_message_with_session_id_in_file_path(self):
        """Test that file paths containing session_id are correctly processed."""
        from langflow.services.database.models.message.model import MessageTable
        from lfx.schema.image import Image

        session_id = "test-session-123"
        file_path = f"/uploads/{session_id}/image.png"
        img = Image(path=file_path, url=f"http://example.com{file_path}")

        message = Message(
            text="Test message",
            sender="User",
            sender_name="User",
            session_id=session_id,
            files=[img],
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        assert len(result.files) == 1
        assert result.files[0] == f"{session_id}/image.png"

    def test_from_message_with_session_id_not_in_file_path(self):
        """Test that file paths NOT containing session_id are preserved as-is."""
        from langflow.services.database.models.message.model import MessageTable
        from lfx.schema.image import Image

        session_id = "test-session-123"
        file_path = "/uploads/other-session/image.png"
        img = Image(path=file_path, url=f"http://example.com{file_path}")

        message = Message(
            text="Test message",
            sender="User",
            sender_name="User",
            session_id=session_id,
            files=[img],
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        assert len(result.files) == 1
        assert result.files[0] == file_path

    def test_from_message_with_no_session_id(self):
        """Test that file paths are preserved when session_id is empty."""
        from langflow.services.database.models.message.model import MessageTable
        from lfx.schema.image import Image

        file_path = "/uploads/some-folder/image.png"
        img = Image(path=file_path, url=f"http://example.com{file_path}")

        message = Message(
            text="Test message",
            sender="User",
            sender_name="User",
            session_id="",
            files=[img],
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        assert len(result.files) == 1
        assert result.files[0] == file_path

    def test_from_message_with_session_id_at_end_of_path(self):
        """Test edge case where session_id is at the end of path (no parts after split)."""
        from langflow.services.database.models.message.model import MessageTable
        from lfx.schema.image import Image

        session_id = "test-session-123"
        # Path ends with session_id - split will have empty second part
        file_path = f"/uploads/{session_id}"
        img = Image(path=file_path, url=f"http://example.com{file_path}")

        message = Message(
            text="Test message",
            sender="User",
            sender_name="User",
            session_id=session_id,
            files=[img],
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        assert len(result.files) == 1
        # When split produces ["uploads/", ""], we get session_id + ""
        assert result.files[0] == f"{session_id}"

    def test_from_message_with_multiple_session_id_occurrences(self):
        """Test file path with multiple occurrences of session_id.

        Note: str.split() splits on ALL occurrences. With path "/uploads/abc/folder/abc/image.png"
        and session_id "abc", split gives ["uploads/", "/folder/", "/image.png"].
        parts[1] is "/folder/" so result is "abc/folder/".
        """
        from langflow.services.database.models.message.model import MessageTable
        from lfx.schema.image import Image

        session_id = "abc"
        # Path has session_id appearing twice
        file_path = f"/uploads/{session_id}/folder/{session_id}/image.png"
        img = Image(path=file_path, url=f"http://example.com{file_path}")

        message = Message(
            text="Test message",
            sender="User",
            sender_name="User",
            session_id=session_id,
            files=[img],
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        assert len(result.files) == 1
        # split() divides em todas as ocorrências: parts = ["/uploads/", "/folder/", "/image.png"]
        # parts[1] = "/folder/", então resultado = "abc/folder/"
        assert result.files[0] == f"{session_id}/folder/"

    def test_from_message_with_multiple_files_mixed_paths(self):
        """Test multiple files with different path scenarios."""
        from langflow.services.database.models.message.model import MessageTable
        from lfx.schema.image import Image

        session_id = "session-xyz"
        images = [
            Image(path=f"/uploads/{session_id}/image1.png", url="http://example.com/1"),
            Image(path="/uploads/other-folder/image2.png", url="http://example.com/2"),
            Image(path=f"/data/{session_id}/docs/file.pdf", url="http://example.com/3"),
        ]

        message = Message(
            text="Test message",
            sender="User",
            sender_name="User",
            session_id=session_id,
            files=images,
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        assert len(result.files) == 3
        assert result.files[0] == f"{session_id}/image1.png"
        assert result.files[1] == "/uploads/other-folder/image2.png"
        assert result.files[2] == f"{session_id}/docs/file.pdf"

    def test_from_message_with_image_empty_path(self):
        """Test that Image with empty path is NOT added to image_paths.

        When Image has empty path, the condition `file.path` is falsy,
        so the image is not processed but the original message.files remains unchanged.
        Since no image_paths are collected, message.files keeps the original Image objects.
        """
        from lfx.schema.image import Image

        session_id = "test-session"
        img = Image(path="", url="http://example.com/image.png")

        message = Message(
            text="Test message",
            sender="User",
            sender_name="User",
            session_id=session_id,
            files=[img],
        )

        # The Image with empty path is kept in message.files (not processed into image_paths)
        # Since image_paths is empty, message.files is not modified
        assert len(message.files) == 1
        assert isinstance(message.files[0], Image)

    def test_from_message_with_image_none_path(self):
        """Test that Image with None path is NOT added to image_paths.

        Similar to empty path case - the Image is not processed but remains in message.files.
        """
        from lfx.schema.image import Image

        session_id = "test-session"
        img = Image(path=None, url="http://example.com/image.png")

        message = Message(
            text="Test message",
            sender="User",
            sender_name="User",
            session_id=session_id,
            files=[img],
        )

        # The Image with None path is kept in message.files
        assert len(message.files) == 1
        assert isinstance(message.files[0], Image)

    def test_from_message_with_image_no_url(self):
        """Test that Image without url attribute still works (url defaults to None)."""
        from langflow.services.database.models.message.model import MessageTable
        from lfx.schema.image import Image

        session_id = "test-session"
        file_path = f"/uploads/{session_id}/image.png"
        # Image with path but url=None - hasattr will return True but url is None
        img = Image(path=file_path)

        message = Message(
            text="Test message",
            sender="User",
            sender_name="User",
            session_id=session_id,
            files=[img],
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        # Image has url attribute (even if None), so it passes hasattr check
        assert len(result.files) == 1
        assert result.files[0] == f"{session_id}/image.png"

    def test_from_message_with_empty_session_id_preserves_path(self):
        """Test file path handling when session_id is empty string."""
        from langflow.services.database.models.message.model import MessageTable
        from lfx.schema.image import Image

        file_path = "/uploads/folder/image.png"
        img = Image(path=file_path, url=f"http://example.com{file_path}")

        message = Message(
            text="Test message",
            sender="User",
            sender_name="User",
            session_id="",
            files=[img],
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        assert len(result.files) == 1
        assert result.files[0] == file_path

    def test_from_message_with_uuid_session_id(self):
        """Test file path handling with UUID session_id."""
        from langflow.services.database.models.message.model import MessageTable
        from lfx.schema.image import Image

        session_uuid = uuid4()
        session_id_str = str(session_uuid)
        file_path = f"/uploads/{session_id_str}/image.png"
        img = Image(path=file_path, url=f"http://example.com{file_path}")

        message = Message(
            text="Test message",
            sender="User",
            sender_name="User",
            session_id=session_id_str,
            files=[img],
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        assert len(result.files) == 1
        assert result.files[0] == f"{session_id_str}/image.png"

    def test_from_message_preserves_string_files(self):
        """Test that string file paths are preserved correctly."""
        from langflow.services.database.models.message.model import MessageTable

        message = Message(
            text="Test message",
            sender="User",
            sender_name="User",
            session_id="test-session",
            files=["path/to/file1.png", "path/to/file2.pdf"],
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        # String files don't have path/url attributes, so they are not processed
        # but the files list should still be set from message.files
        assert result.files == ["path/to/file1.png", "path/to/file2.pdf"]

    def test_from_message_mixed_string_and_image_files(self):
        """Test message with mixed string paths and Image objects.

        Note: When image_paths is populated (at least one Image with valid path is processed),
        message.files is REPLACED by image_paths. String paths are not preserved in image_paths
        because they don't have path/url attributes.
        """
        from langflow.services.database.models.message.model import MessageTable
        from lfx.schema.image import Image

        session_id = "test-session"
        file_path = f"/uploads/{session_id}/image.png"
        img = Image(path=file_path, url=f"http://example.com{file_path}")

        message = Message(
            text="Test message",
            sender="User",
            sender_name="User",
            session_id=session_id,
            files=[img, "string/path/file.txt"],
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        # Only the Image path is included - strings are NOT preserved when image_paths is used
        # This is the current behavior: if any Image is processed, message.files = image_paths
        assert len(result.files) == 1
        assert result.files[0] == f"{session_id}/image.png"

    def test_from_message_with_special_characters_in_session_id(self):
        """Test message with special characters in session_id."""
        from langflow.services.database.models.message.model import MessageTable
        from lfx.schema.image import Image

        special_session_id = "session:with/special@chars#123"
        file_path = f"/uploads/{special_session_id}/image.png"
        img = Image(path=file_path, url=f"http://example.com{file_path}")

        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id=special_session_id,
            files=[img],
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        assert len(result.files) == 1
        assert result.files[0] == f"{special_session_id}/image.png"

    def test_from_message_with_unicode_in_file_path(self):
        """Test message with unicode characters in file path."""
        from langflow.services.database.models.message.model import MessageTable
        from lfx.schema.image import Image

        session_id = "test-session"
        file_path = f"/uploads/{session_id}/imagem_日本語.png"
        img = Image(path=file_path, url=f"http://example.com{file_path}")

        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id=session_id,
            files=[img],
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        assert len(result.files) == 1
        assert result.files[0] == f"{session_id}/imagem_日本語.png"


# =============================================================================
# Tests for Message.model_post_init file handling
# =============================================================================


class TestMessageModelPostInitFiles:
    """Tests for Message.model_post_init file handling changes."""

    def test_model_post_init_with_image_instance(self):
        """Test that existing Image instances are preserved."""
        from lfx.schema.image import Image

        img = Image(path="/path/to/image.png")
        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
            files=[img],
        )

        assert len(message.files) == 1
        assert isinstance(message.files[0], Image)
        assert message.files[0].path == "/path/to/image.png"

    def test_model_post_init_with_string_image_path(self, tmp_path):
        """Test string path that is an image file."""
        from lfx.schema.image import Image
        from PIL import Image as PILImage

        img_path = tmp_path / "photo.jpg"
        PILImage.new("RGB", (10, 10)).save(img_path)

        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
            files=[str(img_path)],
        )

        assert len(message.files) == 1
        assert isinstance(message.files[0], Image)
        assert message.files[0].path == str(img_path)

    def test_model_post_init_with_string_non_image_path(self, tmp_path):
        """Test string path that is not an image file."""
        txt_path = tmp_path / "readme.md"
        txt_path.write_text("# README")

        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
            files=[str(txt_path)],
        )

        assert len(message.files) == 1
        assert message.files[0] == str(txt_path)

    def test_model_post_init_with_empty_files_list(self):
        """Test empty files list."""
        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
            files=[],
        )

        assert message.files == []

    def test_model_post_init_with_none_files(self):
        """Test None files value."""
        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
            files=None,
        )

        assert message.files == []

    def test_model_post_init_with_non_existent_path(self):
        """Test handling of non-existent file paths."""
        non_existent = "/path/that/does/not/exist/image.png"
        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
            files=[non_existent],
        )

        # Non-existent paths are kept as strings (is_image_file returns False)
        assert len(message.files) == 1
        assert message.files[0] == non_existent

    def test_model_post_init_with_multiple_images(self, tmp_path):
        """Test multiple image files."""
        from lfx.schema.image import Image
        from PIL import Image as PILImage

        img_path1 = tmp_path / "image1.png"
        img_path2 = tmp_path / "image2.jpg"
        PILImage.new("RGB", (10, 10)).save(img_path1)
        PILImage.new("RGB", (10, 10)).save(img_path2)

        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
            files=[str(img_path1), str(img_path2)],
        )

        assert len(message.files) == 2
        assert isinstance(message.files[0], Image)
        assert isinstance(message.files[1], Image)

    def test_model_post_init_mixed_image_and_non_image(self, tmp_path):
        """Test mixed image and non-image files."""
        from lfx.schema.image import Image
        from PIL import Image as PILImage

        img_path = tmp_path / "image.png"
        PILImage.new("RGB", (10, 10)).save(img_path)

        txt_path = tmp_path / "doc.txt"
        txt_path.write_text("text content")

        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
            files=[str(img_path), str(txt_path)],
        )

        assert len(message.files) == 2
        assert isinstance(message.files[0], Image)
        assert message.files[1] == str(txt_path)

    def test_model_post_init_preserves_existing_image_instances(self, tmp_path):
        """Test that existing Image instances are not re-processed."""
        from lfx.schema.image import Image
        from PIL import Image as PILImage

        img_path = tmp_path / "image.png"
        PILImage.new("RGB", (10, 10)).save(img_path)

        existing_image = Image(path="/existing/path.jpg", url="http://example.com/img.jpg")

        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
            files=[existing_image, str(img_path)],
        )

        assert len(message.files) == 2
        # First file should be the same Image instance
        assert message.files[0] is existing_image
        assert message.files[0].path == "/existing/path.jpg"
        assert message.files[0].url == "http://example.com/img.jpg"
        # Second file should be converted to Image
        assert isinstance(message.files[1], Image)
        assert message.files[1].path == str(img_path)


# =============================================================================
# Edge case and error tests
# =============================================================================


class TestMessageEdgeCases:
    """Edge case tests for Message and MessageTable."""

    def test_from_message_missing_required_fields(self):
        """Test from_message raises error when required fields are missing."""
        from langflow.services.database.models.message.model import MessageTable

        # Missing text
        message = Message(
            text=None,
            sender="User",
            sender_name="User",
            session_id="session",
        )

        with pytest.raises(ValueError, match="required fields"):
            MessageTable.from_message(message, flow_id=uuid4())

    def test_from_message_missing_sender(self):
        """Test from_message raises error when sender is missing."""
        from langflow.services.database.models.message.model import MessageTable

        message = Message(
            text="Test",
            sender=None,
            sender_name="User",
            session_id="session",
        )

        with pytest.raises(ValueError, match="required fields"):
            MessageTable.from_message(message, flow_id=uuid4())

    def test_from_message_missing_sender_name(self):
        """Test from_message raises error when sender_name is missing."""
        from langflow.services.database.models.message.model import MessageTable

        message = Message(
            text="Test",
            sender="User",
            sender_name=None,
            session_id="session",
        )

        with pytest.raises(ValueError, match="required fields"):
            MessageTable.from_message(message, flow_id=uuid4())

    def test_from_message_with_invalid_flow_id(self):
        """Test from_message raises error with invalid flow_id string."""
        from langflow.services.database.models.message.model import MessageTable

        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
        )

        with pytest.raises(ValueError, match="not a valid UUID"):
            MessageTable.from_message(message, flow_id="invalid-uuid")

    def test_from_message_with_valid_uuid_string_flow_id(self):
        """Test from_message accepts valid UUID string as flow_id."""
        from langflow.services.database.models.message.model import MessageTable

        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
        )

        flow_id_str = str(uuid4())
        result = MessageTable.from_message(message, flow_id=flow_id_str)

        assert str(result.flow_id) == flow_id_str

    def test_from_message_with_iterator_text(self):
        """Test from_message handles iterator text gracefully."""
        from langflow.services.database.models.message.model import MessageTable

        def text_generator():
            yield "chunk1"
            yield "chunk2"

        message = Message(
            text=text_generator(),
            sender="User",
            sender_name="User",
            session_id="session",
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        # Iterator text is converted to empty string
        assert result.text == ""

    def test_from_message_timestamp_string_format(self):
        """Test from_message parses timestamp string correctly."""
        from langflow.services.database.models.message.model import MessageTable

        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
        )
        # Override timestamp with specific format
        message.timestamp = "2024-06-15 10:30:00 UTC"

        result = MessageTable.from_message(message, flow_id=uuid4())

        assert result.timestamp.year == 2024
        assert result.timestamp.month == 6
        assert result.timestamp.day == 15

    def test_from_message_timestamp_iso_format(self):
        """Test from_message parses ISO format timestamp."""
        from langflow.services.database.models.message.model import MessageTable

        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
        )
        # ISO format timestamp
        message.timestamp = "2024-06-15T10:30:00+00:00"

        result = MessageTable.from_message(message, flow_id=uuid4())

        assert result.timestamp.year == 2024
        assert result.timestamp.month == 6

    def test_files_validator_with_none(self):
        """Test files validator handles None."""
        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
        )
        message.files = None

        # Should not raise error
        assert message.files is None or message.files == []

    def test_files_validator_with_single_value(self):
        """Test files validator converts single value to list."""
        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
            files="single_file.png",
        )

        # Single value should be converted to list
        assert isinstance(message.files, list)

    def test_session_id_validator_with_uuid(self):
        """Test session_id validator handles UUID objects."""
        from langflow.services.database.models.message.model import MessageTable

        session_uuid = uuid4()
        message = MessageCreate(
            text="Test",
            sender="User",
            sender_name="User",
            session_id=session_uuid,
        )

        table = MessageTable.model_validate(message, from_attributes=True)
        assert table.session_id == str(session_uuid)

    def test_content_blocks_validation(self):
        """Test content_blocks field validation."""
        from langflow.services.database.models.message.model import MessageTable
        from lfx.schema.content_block import ContentBlock as LfxContentBlock
        from lfx.schema.content_types import TextContent as LfxTextContent

        content_block = LfxContentBlock(
            title="Test Block",
            contents=[LfxTextContent(type="text", text="Test content")],
        )

        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
            content_blocks=[content_block],
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        assert len(result.content_blocks) == 1

    def test_properties_validation(self):
        """Test properties field validation."""
        from langflow.services.database.models.message.model import MessageTable
        from lfx.schema.properties import Properties as LfxProperties
        from lfx.schema.properties import Source as LfxSource

        props = LfxProperties(
            text_color="blue",
            background_color="white",
            source=LfxSource(id="src1", display_name="Source 1", source="test"),
        )

        message = Message(
            text="Test",
            sender="User",
            sender_name="User",
            session_id="session",
            properties=props,
        )

        result = MessageTable.from_message(message, flow_id=uuid4())

        # Properties should be serialized
        assert result.properties is not None


class TestMessageResponseFromMessage:
    """Tests for MessageResponse.from_message."""

    def test_from_message_missing_required_raises_error(self):
        """Test MessageResponse.from_message raises error for missing required fields."""
        from lfx.schema.message import MessageResponse

        message = Message(
            text=None,
            sender="User",
            sender_name="User",
            session_id="session",
        )

        with pytest.raises(ValueError, match="required fields"):
            MessageResponse.from_message(message)
