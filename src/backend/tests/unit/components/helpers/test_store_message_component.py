import pytest

from langflow.components.helpers import MessageStoreComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMessageStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MessageStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "message": "Hello, World!",
            "sender": "User",
            "sender_name": "Alice",
            "session_id": "session_123",
            "memory": None,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "messages", "file_name": "MessageStore"},
            {"version": "1.1.0", "module": "messages", "file_name": "MessageStore"},
        ]

    async def test_store_message_with_memory(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.memory = Mock()  # Mocking the memory input
        result = await component.store_message()
        assert result is not None
        assert result.text == "Hello, World!"
        assert result.sender == "User"
        assert result.sender_name == "Alice"
        assert result.session_id == "session_123"

    async def test_store_message_without_memory(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.memory = None  # No external memory
        result = await component.store_message()
        assert result is not None
        assert result.text == "Hello, World!"
        assert result.sender == "User"
        assert result.sender_name == "Alice"
        assert result.session_id == "session_123"

    async def test_store_message_no_messages_stored(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.memory = None  # No external memory
        with pytest.raises(
            ValueError, match="No messages were stored. Please ensure that the session ID and sender are properly set."
        ):
            await component.store_message()
