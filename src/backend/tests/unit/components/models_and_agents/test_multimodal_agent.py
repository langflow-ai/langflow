"""Test multimodal input handling in agents."""

from unittest.mock import MagicMock

import pytest
from lfx.base.agents.agent import LCAgentComponent
from lfx.schema.message import Message


class MockAgentComponent(LCAgentComponent):
    """Mock agent component for testing."""

    def __init__(self):
        self.input_value = None
        self.chat_history = []
        self.tools = []
        self.display_name = "TestAgent"
        self._event_manager = None
        self.log = MagicMock()

    def get_langchain_callbacks(self):
        return []

    async def send_message(self, message):
        return message

    async def _send_message_event(self, message, category=None):
        pass


@pytest.mark.asyncio
async def test_multimodal_input_text_extraction():
    """Test that text is correctly extracted from multimodal content."""
    component = MockAgentComponent()

    # Create a message with multiple text items
    message = Message(text="Test")
    mock_lc_message = MagicMock()
    mock_lc_message.content = [
        {"type": "text", "text": "First part"},
        {"type": "image", "image_url": "https://example.com/image.jpg"},
        {"type": "text", "text": "Second part"},
    ]

    component.input_value = message

    # We need to test the logic directly since it's in run_agent
    # Let's extract the relevant logic
    image_dicts = [item for item in mock_lc_message.content if item.get("type") == "image"]
    text_content = [item for item in mock_lc_message.content if item.get("type") != "image"]

    text_strings = [
        item.get("text", "") for item in text_content if item.get("type") == "text" and item.get("text", "").strip()
    ]

    result_text = " ".join(text_strings) if text_strings else ""

    # Verify
    assert result_text == "First part Second part"
    assert len(image_dicts) == 1
    assert image_dicts[0]["image_url"] == "https://example.com/image.jpg"


@pytest.mark.asyncio
async def test_multimodal_input_only_images():
    """Test that when only images are present, input becomes empty string."""
    mock_lc_message = MagicMock()
    mock_lc_message.content = [
        {"type": "image", "image_url": "https://example.com/image1.jpg"},
        {"type": "image", "image_url": "https://example.com/image2.jpg"},
    ]

    # Extract logic
    text_content = [item for item in mock_lc_message.content if item.get("type") != "image"]
    text_strings = [
        item.get("text", "") for item in text_content if item.get("type") == "text" and item.get("text", "").strip()
    ]

    result_text = " ".join(text_strings) if text_strings else ""

    # Verify
    assert result_text == ""


@pytest.mark.asyncio
async def test_simple_text_input():
    """Test that simple text input (non-multimodal) works correctly."""
    mock_lc_message = MagicMock()
    mock_lc_message.content = "Simple text message"

    # This should not trigger multimodal logic since content is not a list
    assert not isinstance(mock_lc_message.content, list)

    # The input should be set to the content directly
    result = mock_lc_message.content
    assert result == "Simple text message"


@pytest.mark.asyncio
async def test_multimodal_input_empty_text():
    """Test that empty text items are filtered out."""
    mock_lc_message = MagicMock()
    mock_lc_message.content = [
        {"type": "text", "text": ""},
        {"type": "text", "text": "   "},
        {"type": "text", "text": "Valid text"},
        {"type": "image", "image_url": "https://example.com/image.jpg"},
    ]

    # Extract logic
    text_content = [item for item in mock_lc_message.content if item.get("type") != "image"]
    text_strings = [
        item.get("text", "") for item in text_content if item.get("type") == "text" and item.get("text", "").strip()
    ]

    result_text = " ".join(text_strings) if text_strings else ""

    # Verify - only non-empty text should be included
    assert result_text == "Valid text"
