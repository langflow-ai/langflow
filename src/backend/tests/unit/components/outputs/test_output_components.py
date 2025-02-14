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
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @pytest.fixture
    def module(self):
        """Return the module name for the component."""
        return "outputs"

    @pytest.fixture
    def file_name(self):
        """Return the file name for the component."""
        return "chat"


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
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @pytest.fixture
    def module(self):
        """Return the module name for the component."""
        return "outputs"

    @pytest.fixture
    def file_name(self):
        """Return the file name for the component."""
        return "text"
