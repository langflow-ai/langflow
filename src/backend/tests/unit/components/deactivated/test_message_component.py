import pytest

from langflow.components.deactivated.message import MessageComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMessageComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MessageComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"sender": "user", "sender_name": "John Doe", "session_id": "12345", "text": "Hello, world!"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "messages", "file_name": "Message"},
        ]

    async def test_build_message(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = component.build(**default_kwargs)

        # Assert
        assert result is not None
        assert result.text == "Hello, world!"
        assert result.sender == "user"
        assert result.sender_name == "John Doe"
        assert result.session_id == "12345"

    async def test_build_message_with_ai_sender(self, component_class):
        # Arrange
        default_kwargs = {"sender": "ai", "sender_name": "AI Bot", "session_id": "67890", "text": "Hi there!"}
        component = component_class(**default_kwargs)

        # Act
        result = component.build(**default_kwargs)

        # Assert
        assert result is not None
        assert result.text == "Hi there!"
        assert result.sender == "ai"
        assert result.sender_name == "AI Bot"
        assert result.session_id == "67890"
