import pytest

from langflow.components.outputs import ChatOutput
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestChatOutputComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ChatOutput

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "Hello, World!",
            "should_store_message": True,
            "sender": "AI",
            "sender_name": "ChatBot",
            "session_id": "session_123",
            "data_template": "{text}",
            "background_color": "#FFFFFF",
            "chat_icon": "icon.png",
            "text_color": "#000000",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "chat", "file_name": "ChatOutput"},
            {"version": "1.1.0", "module": "chat", "file_name": "chat_output"},
        ]

    async def test_message_response(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.message_response()

        assert result is not None
        assert result.text == "Hello, World!"
        assert result.sender == "AI"
        assert result.sender_name == "ChatBot"
        assert result.session_id == "session_123"
        assert result.properties.icon == "icon.png"
        assert result.properties.background_color == "#FFFFFF"
        assert result.properties.text_color == "#000000"

    async def test_message_storage(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.message_response()

        assert component.should_store_message is True
        assert component.message.value == result
