import pytest
from langflow.components.outputs import ChatOutput, TextOutputComponent
from langflow.schema.message import Message
from langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI, MESSAGE_SENDER_USER

from tests.base import ComponentTestBaseWithClient, ComponentTestBaseWithoutClient


@pytest.mark.usefixtures("client")
class TestChatOutput(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ChatOutput

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "Hello, how are you?",
            "should_store_message": True,
            "sender": MESSAGE_SENDER_AI,
            "sender_name": MESSAGE_SENDER_NAME_AI,
            "session_id": "test_session_123",
            "data_template": "{text}",
            "background_color": "#f0f0f0",
            "chat_icon": "🤖",
            "text_color": "#000000",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.15", "module": "outputs", "file_name": "ChatOutput"},
            {"version": "1.0.16", "module": "outputs", "file_name": "ChatOutput"},
            {"version": "1.0.17", "module": "outputs", "file_name": "ChatOutput"},
            {"version": "1.0.18", "module": "outputs", "file_name": "ChatOutput"},
            {"version": "1.0.19", "module": "outputs", "file_name": "ChatOutput"},
        ]

    def test_message_response_with_string(self, component_class, default_kwargs):
        """Test message_response with string input."""
        component = component_class(**default_kwargs)
        message = component.message_response()

        assert isinstance(message, Message)
        assert message.text == default_kwargs["input_value"]
        assert message.sender == default_kwargs["sender"]
        assert message.sender_name == default_kwargs["sender_name"]
        assert message.session_id == default_kwargs["session_id"]
        assert message.properties.icon == default_kwargs["chat_icon"]
        assert message.properties.background_color == default_kwargs["background_color"]
        assert message.properties.text_color == default_kwargs["text_color"]

    def test_message_response_with_message(self, component_class):
        """Test message_response with Message input."""
        input_message = Message(
            text="Original message",
            sender=MESSAGE_SENDER_USER,
            sender_name="User",
        )

        kwargs = {
            "input_value": input_message,
            "sender": MESSAGE_SENDER_AI,
            "sender_name": "AI Assistant",
            "session_id": "test_session_123",
        }

        component = component_class(**kwargs)
        result = component.message_response()

        assert isinstance(result, Message)
        assert result.text == "Original message"
        assert result.sender == MESSAGE_SENDER_AI  # Should be overridden
        assert result.sender_name == "AI Assistant"  # Should be overridden

    def test_source_properties(self, component_class, default_kwargs):
        """Test source properties handling."""
        component = component_class(**default_kwargs)
        message = component.message_response()

        assert hasattr(message.properties, "source")
        # Source properties should be empty by default
        assert message.properties.source.dict(exclude_none=True) == {}

    def test_custom_source_properties(self, component_class, default_kwargs):
        """Test custom source properties."""
        source_id = "test_id"
        display_name = "Test Component"
        source = "test_source"

        # Simulate source properties being set
        component = component_class(**default_kwargs)
        source = component._build_source(source_id, display_name, source)

        assert source.id == source_id
        assert source.display_name == display_name
        assert source.source == source

    def test_message_storage_disabled(self, component_class):
        """Test when message storage is disabled."""
        kwargs = {
            "input_value": "Test message",
            "should_store_message": False,
            "sender": MESSAGE_SENDER_AI,
            "session_id": "test_session_123",
        }
        component = component_class(**kwargs)
        message = component.message_response()

        assert isinstance(message, Message)
        assert message.text == "Test message"


class TestTextOutputComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return TextOutputComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "Hello, world!",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.15", "module": "outputs", "file_name": "TextOutput"},
            {"version": "1.0.16", "module": "outputs", "file_name": "TextOutput"},
            {"version": "1.0.17", "module": "outputs", "file_name": "TextOutput"},
            {"version": "1.0.18", "module": "outputs", "file_name": "TextOutput"},
            {"version": "1.0.19", "module": "outputs", "file_name": "TextOutput"},
        ]

    def test_text_response(self, component_class, default_kwargs):
        """Test basic text response."""
        component = component_class(**default_kwargs)
        message = component.text_response()

        assert isinstance(message, Message)
        assert message.text == default_kwargs["input_value"]
        assert component.status == default_kwargs["input_value"]

    def test_empty_input(self, component_class):
        """Test with empty input."""
        component = component_class(input_value="")
        message = component.text_response()

        assert isinstance(message, Message)
        assert message.text == ""
        assert component.status == ""

    def test_non_string_input(self, component_class):
        """Test with non-string input."""
        component = component_class(input_value=42)
        message = component.text_response()

        assert isinstance(message, Message)
        assert message.text == "42"
        assert component.status == 42

    def test_multiline_input(self, component_class):
        """Test with multiline input."""
        multiline_text = "Line 1\nLine 2\nLine 3"
        component = component_class(input_value=multiline_text)
        message = component.text_response()

        assert isinstance(message, Message)
        assert message.text == multiline_text
        assert component.status == multiline_text
        assert len(message.text.split("\n")) == 3
