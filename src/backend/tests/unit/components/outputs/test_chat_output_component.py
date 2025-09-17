import pytest

from lfx.components.input_output import ChatOutput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI
from tests.base import ComponentTestBaseWithClient


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
            "clean_data": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.19", "module": "outputs", "file_name": "ChatOutput"},
            {"version": "1.1.0", "module": "outputs", "file_name": "chat"},
            {"version": "1.1.1", "module": "outputs", "file_name": "chat"},
        ]

    async def test_process_string_input(self, component_class, default_kwargs):
        """Test processing a simple string input."""
        component = component_class(**default_kwargs)
        input_text = "Hello, this is a test message"
        component.input_value = input_text
        result = await component.message_response()
        assert result.text == input_text
        assert result.sender == MESSAGE_SENDER_AI
        assert result.sender_name == MESSAGE_SENDER_NAME_AI

    async def test_process_data_input(self, component_class, default_kwargs):
        """Test processing a Data object input."""
        component = component_class(**default_kwargs)
        data = Data(text="Test data message")
        component.input_value = data
        result = await component.message_response()
        assert result.text == '```json\n{\n  "text": "Test data message"\n}\n```'
        assert result.sender == MESSAGE_SENDER_AI

    async def test_process_dataframe_input(self, component_class, default_kwargs):
        """Test processing a DataFrame input."""
        component = component_class(**default_kwargs)
        sample_df = DataFrame(data={"col1": ["A", "B"], "col2": [1, 2]})
        component.input_value = sample_df
        result = await component.message_response()
        assert "col1" in result.text
        assert "col2" in result.text
        assert "A" in result.text
        assert "B" in result.text

    async def test_process_message_input(self, component_class, default_kwargs):
        """Test processing a Message object input."""
        component = component_class(**default_kwargs)
        message = Message(text="Test message content")
        component.input_value = message
        result = await component.message_response()
        assert result.text == "Test message content"
        assert result.sender == MESSAGE_SENDER_AI

    async def test_process_list_input(self, component_class, default_kwargs):
        """Test processing a list of inputs."""
        component = component_class(**default_kwargs)
        input_list = ["First message", Data(text="Second message"), Message(text="Third message")]
        component.input_value = input_list
        result = await component.message_response()
        assert "First message" in result.text
        assert "Second message" in result.text
        assert "Third message" in result.text

    async def test_invalid_input(self, component_class, default_kwargs):
        """Test handling of invalid input."""
        component = component_class(**default_kwargs)
        component.input_value = None
        with pytest.raises(ValueError, match="Input data cannot be None"):
            await component.message_response()

        component.input_value = 123  # Invalid type
        with pytest.raises(TypeError, match="Expected Data or DataFrame or Message or str, Generator or None"):
            await component.message_response()
