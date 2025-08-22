import enum
from unittest.mock import Mock, patch

import pytest
from langflow.utils.schemas import ChatOutputResponse, ContainsEnumMeta, DataOutputResponse, File
from pydantic import ValidationError


class TestFile:
    """Test cases for File TypedDict."""

    def test_file_typed_dict_structure(self):
        """Test that File TypedDict has correct structure."""
        # TypedDict is mainly for type hints, so we test basic usage
        file_data: File = {"path": "/path/to/file.txt", "name": "file.txt", "type": "txt"}

        assert file_data["path"] == "/path/to/file.txt"
        assert file_data["name"] == "file.txt"
        assert file_data["type"] == "txt"

    def test_file_with_image_type(self):
        """Test File with image type."""
        file_data: File = {"path": "/images/photo.jpg", "name": "photo.jpg", "type": "jpg"}

        assert file_data["type"] == "jpg"

    def test_file_required_fields(self):
        """Test that File requires all specified fields."""
        # This is a compile-time check via TypedDict
        # At runtime, we can still create incomplete dicts
        incomplete_file = {
            "path": "/some/path",
            "name": "filename",
            # missing "type"
        }

        # TypedDict doesn't enforce at runtime, but the schema should require all fields
        assert "path" in incomplete_file
        assert "name" in incomplete_file


class TestChatOutputResponse:
    """Test cases for ChatOutputResponse Pydantic model."""

    def test_basic_chat_response_creation(self):
        """Test creating basic chat response."""
        response = ChatOutputResponse(message="Hello, world!", type="text")

        assert response.message == "Hello, world!"
        assert response.sender == "Machine"  # Default value
        assert response.sender_name == "AI"  # Default value
        assert response.type == "text"
        assert response.files == []
        assert response.session_id is None
        assert response.stream_url is None
        assert response.component_id is None

    def test_chat_response_with_all_fields(self):
        """Test creating chat response with all fields."""
        files = [{"path": "/test.txt", "name": "test.txt", "type": "txt"}]

        response = ChatOutputResponse(
            message="Test message",
            sender="Human",
            sender_name="User",
            session_id="session-123",
            stream_url="http://stream.url",
            component_id="comp-456",
            files=files,
            type="text",
        )

        assert response.message == "Test message"
        assert response.sender == "Human"
        assert response.sender_name == "User"
        assert response.session_id == "session-123"
        assert response.stream_url == "http://stream.url"
        assert response.component_id == "comp-456"
        assert response.files == files
        assert response.type == "text"

    def test_chat_response_with_list_message(self):
        """Test chat response with list message."""
        message_list = ["Hello", {"type": "text", "content": "world"}]

        response = ChatOutputResponse(
            message=message_list,
            sender="Human",  # Use non-AI sender to avoid message validation
            type="mixed",
        )

        assert response.message == message_list

    def test_validate_files_valid_files(self):
        """Test file validation with valid files."""
        files = [
            {"path": "/file1.txt", "name": "file1.txt", "type": "txt"},
            {"path": "/file2.jpg", "name": "file2.jpg", "type": "jpg"},
        ]

        response = ChatOutputResponse(message="Test", files=files, type="text")

        assert len(response.files) == 2
        assert response.files[0]["name"] == "file1.txt"
        assert response.files[1]["type"] == "jpg"

    def test_validate_files_missing_name_and_type(self):
        """Test file validation when name and type are missing."""
        files = [{"path": "/documents/report.pdf"}]

        with (
            patch("langflow.utils.schemas.TEXT_FILE_TYPES", ["pdf", "txt"]),
            patch("langflow.utils.schemas.IMG_FILE_TYPES", ["jpg", "png"]),
        ):
            response = ChatOutputResponse(message="Test", files=files, type="text")

            # Should extract name from path
            assert response.files[0]["name"] == "report.pdf"
            # Should extract type from extension
            assert response.files[0]["type"] == "pdf"

    def test_validate_files_missing_path_raises_error(self):
        """Test that missing path raises validation error."""
        files = [{"name": "file.txt", "type": "txt"}]

        with pytest.raises(ValidationError, match="File path is required"):
            ChatOutputResponse(message="Test", files=files, type="text")

    def test_validate_files_non_dict_raises_error(self):
        """Test that non-dict files raise validation error."""
        files = ["not_a_dict"]

        with pytest.raises(ValidationError, match="Files must be a list of dictionaries"):
            ChatOutputResponse(message="Test", files=files, type="text")

    def test_validate_files_unknown_type_raises_error(self):
        """Test that unknown file type raises validation error."""
        files = [{"path": "/unknown/file.xyz"}]

        with (
            patch("langflow.utils.schemas.TEXT_FILE_TYPES", ["txt"]),
            patch("langflow.utils.schemas.IMG_FILE_TYPES", ["jpg"]),
            pytest.raises(ValidationError, match="File type is required"),
        ):
            ChatOutputResponse(message="Test", files=files, type="text")

    def test_validate_files_empty_list(self):
        """Test validation with empty files list."""
        response = ChatOutputResponse(message="Test", files=[], type="text")

        assert response.files == []

    def test_validate_files_none(self):
        """Test validation with None files."""
        # None is not valid for files field, it should use the default
        response = ChatOutputResponse(message="Test", type="text")

        # Should be set to default empty list
        assert response.files == []

    def test_validate_files_type_detection_in_path(self):
        """Test file type detection when extension not clear but type in path."""
        files = [{"path": "/images/photo_jpg_compressed"}]

        with (
            patch("langflow.utils.schemas.TEXT_FILE_TYPES", ["txt"]),
            patch("langflow.utils.schemas.IMG_FILE_TYPES", ["jpg", "png"]),
        ):
            response = ChatOutputResponse(message="Test", files=files, type="text")

            # Should detect 'jpg' in path
            assert response.files[0]["type"] == "jpg"

    @patch.object(ChatOutputResponse, "__init__")
    def test_from_message_class_method(self, mock_init):
        """Test creating ChatOutputResponse from message."""
        mock_init.return_value = None
        mock_message = Mock()
        mock_message.content = "Hello from message"

        ChatOutputResponse.from_message(mock_message)

        # Verify __init__ was called with correct parameters
        mock_init.assert_called_once_with(message="Hello from message", sender="Machine", sender_name="AI")

    @patch.object(ChatOutputResponse, "__init__")
    def test_from_message_with_custom_sender(self, mock_init):
        """Test creating ChatOutputResponse from message with custom sender."""
        mock_init.return_value = None
        mock_message = Mock()
        mock_message.content = "Custom message"

        ChatOutputResponse.from_message(mock_message, sender="Human", sender_name="User")

        # Verify __init__ was called with correct parameters
        mock_init.assert_called_once_with(message="Custom message", sender="Human", sender_name="User")

    def test_validate_message_ai_sender_newline_formatting(self):
        """Test message validation for AI sender with newline formatting."""
        response = ChatOutputResponse(message="Line 1\nLine 2\nLine 3", sender="Machine", type="text")

        # Should convert single \n to \n\n for markdown compliance
        expected_message = "Line 1\n\nLine 2\n\nLine 3"
        assert response.message == expected_message

    def test_validate_message_ai_sender_existing_double_newlines(self):
        """Test message validation with existing double newlines."""
        response = ChatOutputResponse(message="Line 1\n\nLine 2\n\nLine 3", sender="Machine", type="text")

        # Should not add extra newlines where double newlines already exist
        expected_message = "Line 1\n\nLine 2\n\nLine 3"
        assert response.message == expected_message

    def test_validate_message_non_ai_sender_unchanged(self):
        """Test that non-AI sender messages are unchanged."""
        original_message = "Line 1\nLine 2\nLine 3"
        response = ChatOutputResponse(message=original_message, sender="Human", type="text")

        # Should remain unchanged for non-AI senders
        assert response.message == original_message

    def test_validate_message_complex_newline_patterns(self):
        """Test message validation with complex newline patterns."""
        response = ChatOutputResponse(
            message="Para 1\n\nPara 2\nLine in para 2\n\n\nPara 3", sender="Machine", type="text"
        )

        # The actual logic: replace \n\n with \n, then replace \n with \n\n
        # "Para 1\n\nPara 2\nLine in para 2\n\n\nPara 3"
        # -> "Para 1\nPara 2\nLine in para 2\n\nPara 3" (replace \n\n with \n)
        # -> "Para 1\n\nPara 2\n\nLine in para 2\n\n\n\nPara 3" (replace \n with \n\n)
        expected_message = "Para 1\n\nPara 2\n\nLine in para 2\n\n\n\nPara 3"
        assert response.message == expected_message

    def test_message_validation_with_list_message(self):
        """Test message validation when message is a list."""
        message_list = ["Hello", "World"]
        response = ChatOutputResponse(
            message=message_list,
            sender="Human",  # Use non-AI sender to avoid validation error
            type="text",
        )

        # List messages should not be processed for newlines when sender is not AI
        assert response.message == message_list


class TestDataOutputResponse:
    """Test cases for DataOutputResponse Pydantic model."""

    def test_basic_data_response_creation(self):
        """Test creating basic data output response."""
        data = [{"key": "value"}, {"another": "item"}]

        response = DataOutputResponse(data=data)

        assert response.data == data

    def test_data_response_with_none_values(self):
        """Test data response with None values in list."""
        data = [{"key": "value"}, None, {"another": "item"}]

        response = DataOutputResponse(data=data)

        assert response.data == data
        assert response.data[1] is None

    def test_data_response_empty_list(self):
        """Test data response with empty list."""
        response = DataOutputResponse(data=[])

        assert response.data == []

    def test_data_response_all_none(self):
        """Test data response with all None values."""
        data = [None, None, None]

        response = DataOutputResponse(data=data)

        assert response.data == data
        assert all(item is None for item in response.data)

    def test_data_response_complex_dicts(self):
        """Test data response with complex dictionary structures."""
        data = [{"nested": {"key": "value"}, "list": [1, 2, 3], "number": 42, "boolean": True}, {"simple": "string"}]

        response = DataOutputResponse(data=data)

        assert response.data == data
        assert response.data[0]["nested"]["key"] == "value"
        assert response.data[0]["list"] == [1, 2, 3]


class TestContainsEnumMeta:
    """Test cases for ContainsEnumMeta metaclass."""

    def test_enum_with_contains_meta(self):
        """Test enum using ContainsEnumMeta."""

        class TestEnum(enum.Enum, metaclass=ContainsEnumMeta):
            VALUE_A = "a"
            VALUE_B = "b"
            VALUE_C = "c"

        # Test contains functionality
        assert "a" in TestEnum
        assert "b" in TestEnum
        assert "c" in TestEnum
        assert "d" not in TestEnum
        assert "invalid" not in TestEnum

    def test_enum_contains_with_different_types(self):
        """Test enum contains with different value types."""

        class MixedEnum(enum.Enum, metaclass=ContainsEnumMeta):
            STRING_VAL = "string"
            INT_VAL = 42
            FLOAT_VAL = 3.14

        assert "string" in MixedEnum
        assert 42 in MixedEnum
        assert 3.14 in MixedEnum
        assert "not_string" not in MixedEnum
        assert 999 not in MixedEnum

    def test_enum_contains_with_duplicate_values(self):
        """Test enum contains when enum has aliases."""

        class AliasEnum(enum.Enum, metaclass=ContainsEnumMeta):
            FIRST = "value"
            SECOND = "value"  # Alias for FIRST  # noqa: PIE796
            THIRD = "other"

        assert "value" in AliasEnum
        assert "other" in AliasEnum
        assert "nonexistent" not in AliasEnum

    def test_enum_contains_error_handling(self):
        """Test that contains handles ValueError gracefully."""

        class StrictEnum(enum.Enum, metaclass=ContainsEnumMeta):
            def __new__(cls, value):
                if not isinstance(value, str):
                    msg = "Only strings allowed"
                    raise TypeError(msg)
                obj = object.__new__(cls)
                obj._value_ = value
                return obj

            VALID = "valid"

        assert "valid" in StrictEnum
        assert 123 not in StrictEnum  # Should return False, not raise

    def test_enum_normal_functionality_preserved(self):
        """Test that normal enum functionality is preserved."""

        class NormalEnum(enum.Enum, metaclass=ContainsEnumMeta):
            OPTION_1 = "opt1"
            OPTION_2 = "opt2"

        # Normal enum operations should still work
        assert NormalEnum.OPTION_1.value == "opt1"
        assert NormalEnum("opt1") == NormalEnum.OPTION_1
        assert list(NormalEnum) == [NormalEnum.OPTION_1, NormalEnum.OPTION_2]

    def test_enum_inheritance_with_contains_meta(self):
        """Test enum inheritance with ContainsEnumMeta."""

        class BaseEnum(enum.Enum, metaclass=ContainsEnumMeta):
            BASE_VALUE = "base"

        # Test that the metaclass works for the base enum
        assert "base" in BaseEnum
        assert "invalid" not in BaseEnum
