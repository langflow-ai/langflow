import base64

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langflow.schema.data import Data
from langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER


@pytest.fixture
def sample_image(tmp_path):
    """Create a sample image file for testing."""
    image_path = tmp_path / "test_image.png"
    # Create a small black 1x1 pixel PNG file
    image_content = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    image_path.write_bytes(image_content)
    return image_path


class TestDataSchema:
    def test_data_to_message_with_text_only(self):
        """Test conversion of Data to Message with text only."""
        data = Data(data={"text": "Hello, world!", "sender": MESSAGE_SENDER_USER})
        message = data.to_lc_message()
        assert isinstance(message, HumanMessage)
        assert message.content == [{"type": "text", "text": "Hello, world!"}]

    def test_data_to_message_with_image(self, sample_image):
        """Test conversion of Data to Message with text and image."""
        data = Data(data={"text": "Check out this image", "sender": MESSAGE_SENDER_USER, "files": [str(sample_image)]})
        message = data.to_lc_message()

        assert isinstance(message, HumanMessage)
        assert isinstance(message.content, list)
        assert len(message.content) == 2

        # Check text content
        assert message.content[0] == {"type": "text", "text": "Check out this image"}

        # Check image content
        assert message.content[1]["type"] == "image"
        assert message.content[1]["source_type"] == "url"
        assert "url" in message.content[1]
        assert message.content[1]["url"].startswith("data:image/png;base64,")

    def test_data_to_message_with_multiple_images(self, sample_image, tmp_path):
        """Test conversion of Data to Message with multiple images."""
        # Create a second image
        second_image = tmp_path / "second_image.png"
        second_image.write_bytes(sample_image.read_bytes())

        data = Data(
            data={
                "text": "Multiple images",
                "sender": MESSAGE_SENDER_USER,
                "files": [str(sample_image), str(second_image)],
            }
        )
        message = data.to_lc_message()

        assert isinstance(message, HumanMessage)
        assert isinstance(message.content, list)
        assert len(message.content) == 3  # text + 2 images

        # Check text content
        assert message.content[0]["type"] == "text"

        # Check both images
        assert message.content[1]["type"] == "image"
        assert message.content[1]["source_type"] == "url"
        assert "url" in message.content[1]
        assert message.content[1]["url"].startswith("data:image/png;base64,")

        assert message.content[2]["type"] == "image"
        assert message.content[2]["source_type"] == "url"
        assert "url" in message.content[2]
        assert message.content[2]["url"].startswith("data:image/png;base64,")

    def test_data_to_message_ai_response(self):
        """Test conversion of Data to AI Message."""
        data = Data(data={"text": "AI response", "sender": MESSAGE_SENDER_AI})
        message = data.to_lc_message()
        assert isinstance(message, AIMessage)
        assert message.content == "AI response"

    def test_data_to_message_missing_required_keys(self):
        """Test conversion fails with missing required keys."""
        data = Data(data={"incomplete": "data"})
        with pytest.raises(ValueError, match="Missing required keys"):
            data.to_lc_message()

    def test_data_to_message_invalid_image_path(self, tmp_path):
        """Test handling of invalid image path."""
        non_existent_image = tmp_path / "non_existent.png"
        data = Data(data={"text": "Invalid image", "sender": MESSAGE_SENDER_USER, "files": [str(non_existent_image)]})

        with pytest.raises(FileNotFoundError):
            data.to_lc_message()
