import base64
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from loguru import logger
from platformdirs import user_cache_dir

from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER


@pytest.fixture
def langflow_cache_dir(tmp_path):
    """Create a temporary langflow cache directory."""
    cache_dir = tmp_path / "langflow"
    cache_dir.mkdir(parents=True)
    return cache_dir


@pytest.fixture
def sample_image(langflow_cache_dir):
    """Create a sample image file for testing."""
    # Create the test_flow directory in the cache
    flow_dir = langflow_cache_dir / "test_flow"
    flow_dir.mkdir(parents=True, exist_ok=True)

    # Create the image in the flow directory
    image_path = flow_dir / "test_image.png"
    # Create a small black 1x1 pixel PNG file
    image_content = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    image_path.write_bytes(image_content)

    # Use platformdirs to get the cache directory
    real_cache_dir = Path(user_cache_dir("langflow"))
    real_cache_dir.mkdir(parents=True, exist_ok=True)
    real_flow_dir = real_cache_dir / "test_flow"
    real_flow_dir.mkdir(parents=True, exist_ok=True)

    # Copy the image to the real cache location
    real_image_path = real_flow_dir / "test_image.png"
    shutil.copy2(str(image_path), str(real_image_path))

    return image_path


def test_message_prompt_serialization():
    template = "Hello, {name}!"
    message = Message.from_template(template, name="Langflow")
    assert message.text == "Hello, Langflow!"

    # The base Message class in lfx doesn't support prompt serialization
    # This functionality is only available in the enhanced message class
    pytest.skip("Prompt serialization not supported in lfx base Message class")


def test_message_from_human_text():
    """Test creating a message from human text."""
    text = "Hello, AI!"
    message = Message(text=text, sender=MESSAGE_SENDER_USER)
    lc_message = message.to_lc_message()

    assert isinstance(lc_message, HumanMessage)
    assert isinstance(lc_message.content, str)
    assert lc_message.content == text


def test_message_from_ai_text():
    """Test creating a message from AI text."""
    text = "Hello, Human!"
    message = Message(text=text, sender=MESSAGE_SENDER_AI)
    lc_message = message.to_lc_message()

    assert isinstance(lc_message, AIMessage)
    assert lc_message.content == text


def test_message_with_single_image(sample_image):
    """Test creating a message with text and an image."""
    text = "Check out this image"
    # Format the file path as expected: "flow_id/filename"
    file_path = f"test_flow/{sample_image.name}"
    message = Message(text=text, sender=MESSAGE_SENDER_USER, files=[file_path])
    lc_message = message.to_lc_message()

    # The base Message class in lfx only supports simple text content
    # Image content is handled in the enhanced message class
    assert isinstance(lc_message, HumanMessage)
    assert isinstance(lc_message.content, str)
    assert lc_message.content == text

    # Verify the message object has files
    assert message.files == [file_path]


def test_message_with_multiple_images(sample_image, langflow_cache_dir):
    """Test creating a message with multiple images."""
    # Create a second image in the cache directory
    flow_dir = langflow_cache_dir / "test_flow"
    second_image = flow_dir / "second_image.png"
    shutil.copy2(str(sample_image), str(second_image))

    # Use platformdirs for the real cache location
    real_cache_dir = Path(user_cache_dir("langflow")) / "test_flow"
    real_cache_dir.mkdir(parents=True, exist_ok=True)
    real_second_image = real_cache_dir / "second_image.png"
    shutil.copy2(str(sample_image), str(real_second_image))

    text = "Multiple images"
    message = Message(
        text=text,
        sender=MESSAGE_SENDER_USER,
        files=[f"test_flow/{sample_image.name}", f"test_flow/{second_image.name}"],
    )
    lc_message = message.to_lc_message()

    # The base Message class in lfx only supports simple text content
    assert isinstance(lc_message, HumanMessage)
    assert isinstance(lc_message.content, str)
    assert lc_message.content == text

    # Verify the message object has the files
    assert len(message.files) == 2
    assert f"test_flow/{sample_image.name}" in message.files
    assert f"test_flow/{second_image.name}" in message.files


def test_message_with_invalid_image_path():
    """Test handling of invalid image path."""
    file_path = "test_flow/non_existent.png"
    message = Message(text="Invalid image", sender=MESSAGE_SENDER_USER, files=[file_path])

    # The base Message class doesn't validate file paths in to_lc_message()
    # It just returns the text content
    lc_message = message.to_lc_message()
    assert isinstance(lc_message, HumanMessage)
    assert lc_message.content == "Invalid image"

    # The invalid file path is still stored in the message
    assert message.files == [file_path]


def test_message_without_sender():
    """Test message creation without sender specification."""
    # Create message without sender
    message = Message(text="Test message")
    # Verify the message was created but has no sender
    assert message.text == "Test message"
    assert message.sender is None


def test_message_serialization():
    """Test message serialization to dict."""
    # Create a timestamp with timezone
    message = Message(text="Test message", sender=MESSAGE_SENDER_USER)
    timestamp_str = message.timestamp
    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S %Z").replace(tzinfo=timezone.utc)
    serialized = message.model_dump()

    assert serialized["text"] == "Test message"
    assert serialized["sender"] == MESSAGE_SENDER_USER
    assert serialized["timestamp"] == timestamp
    assert serialized["timestamp"].tzinfo == timezone.utc


def test_message_to_lc_without_sender():
    """Test converting a message without sender to langchain message."""
    message = Message(text="Test message")
    # When no sender is specified, it defaults to AIMessage
    lc_message = message.to_lc_message()
    assert isinstance(lc_message, HumanMessage)


def test_timestamp_serialization():
    """Test timestamp serialization with different formats."""
    # Test with timezone
    msg1 = Message(text="Test message", sender=MESSAGE_SENDER_USER, timestamp="2023-12-25 15:30:45 UTC")
    serialized1 = msg1.model_dump()
    assert serialized1["timestamp"].tzinfo == timezone.utc

    # Test without timezone
    msg2 = Message(text="Test message", sender=MESSAGE_SENDER_USER, timestamp="2023-12-25 15:30:45")
    serialized2 = msg2.model_dump()
    assert serialized2["timestamp"].tzinfo == timezone.utc

    # Test that both formats result in equivalent UTC times when appropriate
    msg_with_tz = Message(text="Test message", sender=MESSAGE_SENDER_USER, timestamp="2023-12-25 15:30:45 UTC")
    msg_without_tz = Message(text="Test message", sender=MESSAGE_SENDER_USER, timestamp="2023-12-25 15:30:45")
    assert msg_with_tz.model_dump()["timestamp"] == msg_without_tz.model_dump()["timestamp"]


# Clean up the cache directory after all tests
@pytest.fixture(autouse=True)
def cleanup():
    yield
    # Clean up the real cache directory after tests
    cache_dir = Path(user_cache_dir("langflow"))
    if cache_dir.exists():
        try:
            shutil.rmtree(str(cache_dir))
        except OSError as exc:
            logger.error(f"Error cleaning up cache directory: {exc}")
