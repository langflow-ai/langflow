import pytest
from langflow.components.inputs import ChatInput

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestChatInputComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ChatInput

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "Hello, how can I help you?",
            "should_store_message": True,
            "sender": "user",
            "sender_name": "John Doe",
            "session_id": "session_123",
            "files": [],
            "background_color": "#FFFFFF",
            "chat_icon": "icon.png",
            "text_color": "#000000",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "chat", "file_name": "ChatInput"},
        ]

    async def test_message_response(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        result = await component.message_response()
        assert result is not None
        assert result.text == default_kwargs["input_value"]
        assert result.sender == default_kwargs["sender"]
        assert result.sender_name == default_kwargs["sender_name"]
        assert result.session_id == default_kwargs["session_id"]
        assert result.properties["background_color"] == default_kwargs["background_color"]
        assert result.properties["text_color"] == default_kwargs["text_color"]
        assert result.properties["icon"] == default_kwargs["chat_icon"]

    async def test_should_store_message(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        result = await component.message_response()
        assert component.should_store_message is True
        assert component.message.value == result
