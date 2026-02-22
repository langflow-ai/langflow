import base64
import json
from decimal import Decimal

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from lfx.schema.data import Data, serialize_data
from lfx.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER


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
        expected_content_len = 2
        assert len(message.content) == expected_content_len

        # Check text content
        text_content = message.content[0]
        assert text_content == {"type": "text", "text": "Check out this image"}

        # Check image content
        assert message.content[1]["type"] == "image_url"
        assert "image_url" in message.content[1]
        assert "url" in message.content[1]["image_url"]
        assert message.content[1]["image_url"]["url"].startswith("data:image/png;base64,")

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
        expected_content_len = 3  # text + 2 images
        assert len(message.content) == expected_content_len

        # Check text content
        text_content = message.content[0]
        assert text_content["type"] == "text"

        # Check both images
        assert message.content[1]["type"] == "image_url"
        assert "image_url" in message.content[1]
        assert "url" in message.content[1]["image_url"]
        assert message.content[1]["image_url"]["url"].startswith("data:image/png;base64,")

        assert message.content[2]["type"] == "image_url"
        assert "image_url" in message.content[2]
        assert "url" in message.content[2]["image_url"]
        assert message.content[2]["image_url"]["url"].startswith("data:image/png;base64,")

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


class TestDataNanSerialization:
    """Tests for NaN/Infinity sanitization during Data serialization."""

    def test_nan_and_infinity_serialized_as_null(self):
        """Test that top-level NaN and Infinity values become null in JSON."""
        data = Data(
            data={
                "text": "search result",
                "score": float("nan"),
                "positive_inf": float("inf"),
                "negative_inf": float("-inf"),
                "normal_float": 0.95,
            }
        )
        result = serialize_data(data.data)
        parsed = json.loads(result)

        assert parsed["score"] is None
        assert parsed["positive_inf"] is None
        assert parsed["negative_inf"] is None
        assert parsed["normal_float"] == 0.95

    def test_nan_in_nested_list(self):
        """Test that NaN inside a list is sanitized."""
        data = Data(data={"scores": [0.5, float("nan"), 0.8]})
        result = serialize_data(data.data)
        parsed = json.loads(result)

        assert parsed["scores"] == [0.5, None, 0.8]

    def test_nan_in_nested_dict(self):
        """Test that NaN inside a nested dict is sanitized."""
        data = Data(data={"meta": {"score": float("nan"), "name": "test"}})
        result = serialize_data(data.data)
        parsed = json.loads(result)

        assert parsed["meta"]["score"] is None
        assert parsed["meta"]["name"] == "test"

    def test_nan_in_list_of_dicts(self):
        """Test that NaN in a list of dicts (common search result shape) is sanitized."""
        data = Data(
            data={
                "results": [
                    {"title": "result1", "score": float("inf")},
                    {"title": "result2", "score": 0.7},
                ]
            }
        )
        result = serialize_data(data.data)
        parsed = json.loads(result)

        assert parsed["results"][0]["score"] is None
        assert parsed["results"][1]["score"] == 0.7

    def test_decimal_nan_serialized_as_null(self):
        """Test that Decimal('NaN') is sanitized via custom_serializer."""
        data = Data(data={"value": Decimal("NaN"), "normal": Decimal("1.5")})
        result = serialize_data(data.data)
        parsed = json.loads(result)

        assert parsed["value"] is None
        assert parsed["normal"] == 1.5

    def test_str_path_sanitizes_nan(self):
        """Test that str(data) produces valid JSON when data contains NaN."""
        data = Data(data={"score": float("nan"), "text": "hello"})
        result = str(data)
        parsed = json.loads(result)

        assert parsed["score"] is None
        assert parsed["text"] == "hello"

    def test_model_dump_json_sanitizes_nan(self):
        """Test that model_dump_json() produces valid JSON when data contains NaN."""
        data = Data(data={"score": float("nan"), "text": "hello"})
        result = data.model_dump_json()
        parsed = json.loads(result)

        assert parsed["score"] is None
        assert parsed["text"] == "hello"

    def test_normal_values_preserved(self):
        """Test that normal values pass through sanitization unchanged."""
        data = Data(
            data={
                "string": "hello",
                "int": 42,
                "float": 3.14,
                "bool": True,
                "none": None,
                "list": [1, "two", 3.0],
            }
        )
        result = serialize_data(data.data)
        parsed = json.loads(result)

        assert parsed["string"] == "hello"
        assert parsed["int"] == 42
        assert parsed["float"] == 3.14
        assert parsed["bool"] is True
        assert parsed["none"] is None
        assert parsed["list"] == [1, "two", 3.0]
