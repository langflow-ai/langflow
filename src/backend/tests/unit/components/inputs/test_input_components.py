import pytest
from langflow.components.inputs import ChatInput, TextInputComponent
from langflow.schema.message import Message
from langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_USER, MESSAGE_SENDER_USER

from tests.base import ComponentTestBaseWithClient, ComponentTestBaseWithoutClient


@pytest.mark.usefixtures("client")
class TestChatInput(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ChatInput

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "Hello, how are you?",
            "should_store_message": True,
            "sender": MESSAGE_SENDER_USER,
            "sender_name": MESSAGE_SENDER_NAME_USER,
            "session_id": "test_session_123",
            "files": [],
            "background_color": "#f0f0f0",
            "chat_icon": "👤",
            "text_color": "#000000",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.15", "module": "inputs", "file_name": "ChatInput"},
            {"version": "1.0.16", "module": "inputs", "file_name": "ChatInput"},
            {"version": "1.0.17", "module": "inputs", "file_name": "ChatInput"},
            {"version": "1.0.18", "module": "inputs", "file_name": "ChatInput"},
            {"version": "1.0.19", "module": "inputs", "file_name": "ChatInput"},
        ]

    def test_message_response(self, component_class, default_kwargs):
        """Test that the message_response method returns a valid Message object."""
        component = component_class(**default_kwargs)
        message = component.message_response()

        assert isinstance(message, Message)
        assert message.text == default_kwargs["input_value"]
        assert message.sender == default_kwargs["sender"]
        assert message.sender_name == default_kwargs["sender_name"]
        assert message.session_id == default_kwargs["session_id"]
        assert message.files == default_kwargs["files"]
        assert message.properties == {
            "background_color": default_kwargs["background_color"],
            "text_color": default_kwargs["text_color"],
            "icon": default_kwargs["chat_icon"],
        }

    def test_message_response_ai_sender(self, component_class):
        """Test message response with AI sender type."""
        kwargs = {
            "input_value": "I am an AI assistant",
            "sender": MESSAGE_SENDER_AI,
            "sender_name": "AI Assistant",
            "session_id": "test_session_123",
        }
        component = component_class(**kwargs)
        message = component.message_response()

        assert isinstance(message, Message)
        assert message.sender == MESSAGE_SENDER_AI
        assert message.sender_name == "AI Assistant"

    def test_message_response_without_session(self, component_class):
        """Test message response without session ID."""
        kwargs = {
            "input_value": "Test message",
            "sender": MESSAGE_SENDER_USER,
            "sender_name": MESSAGE_SENDER_NAME_USER,
            "session_id": "",  # Empty session ID
        }
        component = component_class(**kwargs)
        message = component.message_response()

        assert isinstance(message, Message)
        assert message.session_id == ""

    def test_message_response_with_files(self, component_class, tmp_path):
        """Test message response with file attachments."""
        # Create a temporary test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        kwargs = {
            "input_value": "Message with file",
            "sender": MESSAGE_SENDER_USER,
            "sender_name": MESSAGE_SENDER_NAME_USER,
            "session_id": "test_session_123",
            "files": [str(test_file)],
        }
        component = component_class(**kwargs)
        message = component.message_response()

        assert isinstance(message, Message)
        assert len(message.files) == 1
        assert message.files[0] == str(test_file)

    def test_message_storage_disabled(self, component_class):
        """Test message response when storage is disabled."""
        kwargs = {
            "input_value": "Test message",
            "should_store_message": False,
            "sender": MESSAGE_SENDER_USER,
            "sender_name": MESSAGE_SENDER_NAME_USER,
            "session_id": "test_session_123",
        }
        component = component_class(**kwargs)
        message = component.message_response()

        assert isinstance(message, Message)
        # The message should still be created but not stored
        assert message.text == "Test message"


class TestTextInputComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return TextInputComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "Hello, world!",
            "data_template": "{text}",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.15", "module": "inputs", "file_name": "TextComponent"},
            {"version": "1.0.16", "module": "inputs", "file_name": "TextComponent"},
            {"version": "1.0.17", "module": "inputs", "file_name": "TextComponent"},
            {"version": "1.0.18", "module": "inputs", "file_name": "TextComponent"},
            {"version": "1.0.19", "module": "inputs", "file_name": "TextComponent"},
        ]

    def test_text_output(self, component_class, default_kwargs):
        """Test basic text output."""
        component = component_class(**default_kwargs)
        result = component()
        assert result == "Hello, world!"

    def test_empty_input(self, component_class):
        """Test component with empty input."""
        component = component_class(input_value="")
        result = component()
        assert result == ""

    def test_data_template_with_dict(self, component_class):
        """Test component with dictionary input and template."""
        test_data = {"text": "Hello", "name": "John"}
        component = component_class(input_value=test_data, data_template="Message: {text}, Name: {name}")
        result = component()
        assert result == "Message: Hello, Name: John"

    def test_data_template_empty(self, component_class):
        """Test component with dictionary input but no template."""
        test_data = {"text": "Hello World"}
        component = component_class(
            input_value=test_data,
            data_template="",  # Empty template should default to {text}
        )
        result = component()
        assert result == "Hello World"

    def test_non_string_input(self, component_class):
        """Test component with non-string input."""
        component = component_class(input_value=42)
        result = component()
        assert result == "42"

    def test_complex_template(self, component_class):
        """Test component with complex template and nested data."""
        test_data = {"user": {"name": "John", "age": 30}, "message": "Hello"}
        component = component_class(
            input_value=test_data, data_template="User {user[name]} ({user[age]}) says: {message}"
        )
        result = component()
        assert result == "User John (30) says: Hello"