import pytest
from langflow.components.outputs import ChatOutput, TextOutputComponent
from langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI

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
            {"version": "1.0.17", "module": "outputs", "file_name": "TextOutput"},
            {"version": "1.0.18", "module": "outputs", "file_name": "TextOutput"},
            {"version": "1.0.19", "module": "outputs", "file_name": "TextOutput"},
        ]
