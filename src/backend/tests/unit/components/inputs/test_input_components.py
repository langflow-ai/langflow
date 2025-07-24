import pytest
from anyio import Path

from lfx.components.input_output import ChatInput, TextInputComponent
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_USER, MESSAGE_SENDER_USER
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
            {"version": "1.0.19", "module": "inputs", "file_name": "ChatInput"},
            {"version": "1.1.0", "module": "inputs", "file_name": "chat"},
            {"version": "1.1.1", "module": "inputs", "file_name": "chat"},
        ]

    async def test_message_response(self, component_class, default_kwargs):
        """Test that the message_response method returns a valid Message object."""
        component = component_class(**default_kwargs)
        message = await component.message_response()

        assert isinstance(message, Message)
        assert message.text == default_kwargs["input_value"]
        assert message.sender == default_kwargs["sender"]
        assert message.sender_name == default_kwargs["sender_name"]
        assert message.session_id == default_kwargs["session_id"]
        assert message.files == default_kwargs["files"]
        assert message.properties.model_dump() == {
            "background_color": default_kwargs["background_color"],
            "text_color": default_kwargs["text_color"],
            "icon": default_kwargs["chat_icon"],
            "positive_feedback": None,
            "edited": False,
            "source": {"id": None, "display_name": None, "source": None},
            "allow_markdown": False,
            "state": "complete",
            "targets": [],
        }

    async def test_message_response_ai_sender(self, component_class):
        """Test message response with AI sender type."""
        kwargs = {
            "input_value": "I am an AI assistant",
            "sender": MESSAGE_SENDER_AI,
            "sender_name": "AI Assistant",
            "session_id": "test_session_123",
        }
        component = component_class(**kwargs)
        message = await component.message_response()

        assert isinstance(message, Message)
        assert message.sender == MESSAGE_SENDER_AI
        assert message.sender_name == "AI Assistant"

    async def test_message_response_without_session(self, component_class):
        """Test message response without session ID."""
        kwargs = {
            "input_value": "Test message",
            "sender": MESSAGE_SENDER_USER,
            "sender_name": MESSAGE_SENDER_NAME_USER,
            "session_id": "",  # Empty session ID
        }
        component = component_class(**kwargs)
        message = await component.message_response()

        assert isinstance(message, Message)
        assert message.session_id == ""

    async def test_message_response_with_files(self, component_class, tmp_path):
        """Test message response with file attachments."""
        # Create a temporary test file
        test_file = Path(tmp_path) / "test.txt"
        await test_file.write_text("Test content", encoding="utf-8")

        kwargs = {
            "input_value": "Message with file",
            "sender": MESSAGE_SENDER_USER,
            "sender_name": MESSAGE_SENDER_NAME_USER,
            "session_id": "test_session_123",
            "files": [str(test_file)],
        }
        component = component_class(**kwargs)
        message = await component.message_response()

        assert isinstance(message, Message)
        assert len(message.files) == 1
        assert message.files[0] == str(test_file)

    async def test_message_storage_disabled(self, component_class):
        """Test message response when storage is disabled."""
        kwargs = {
            "input_value": "Test message",
            "should_store_message": False,
            "sender": MESSAGE_SENDER_USER,
            "sender_name": MESSAGE_SENDER_NAME_USER,
            "session_id": "test_session_123",
        }
        component = component_class(**kwargs)
        message = await component.message_response()

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
            {"version": "1.0.19", "module": "inputs", "file_name": "TextInput"},
            {"version": "1.1.0", "module": "inputs", "file_name": "text"},
            {"version": "1.1.1", "module": "inputs", "file_name": "text"},
        ]
