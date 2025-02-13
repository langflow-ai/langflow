import pytest

from langflow.components.helpers import MemoryComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMemoryComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MemoryComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "memory": None,
            "sender": "Machine and User",
            "sender_name": "John",
            "n_messages": 5,
            "session_id": "123",
            "order": "Ascending",
            "template": "{sender_name}: {text}",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "memory", "file_name": "Memory"},
            {"version": "1.1.0", "module": "memory", "file_name": "memory"},
        ]

    async def test_retrieve_messages(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.retrieve_messages()
        assert result is not None
        assert isinstance(result, list)
        assert len(result) <= default_kwargs["n_messages"]

    async def test_retrieve_messages_as_text(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.retrieve_messages_as_text()
        assert result is not None
        assert isinstance(result, Message)
        assert "{sender_name}" in result.text
        assert "{text}" in result.text

    async def test_memory_with_external_memory(self, component_class, default_kwargs):
        # Mocking external memory behavior
        mock_memory = Mock()
        mock_memory.aget_messages = AsyncMock(
            return_value=[
                {"text": "Hello", "type": MESSAGE_SENDER_USER},
                {"text": "Hi", "type": MESSAGE_SENDER_AI},
            ]
        )
        default_kwargs["memory"] = mock_memory

        component = component_class(**default_kwargs)
        result = await component.retrieve_messages()
        assert len(result) == 2
        assert all(isinstance(msg, Message) for msg in result)

    async def test_ordering_of_messages(self, component_class, default_kwargs):
        # Mocking external memory behavior
        mock_memory = Mock()
        mock_memory.aget_messages = AsyncMock(
            return_value=[
                {"text": "First", "type": MESSAGE_SENDER_USER},
                {"text": "Second", "type": MESSAGE_SENDER_AI},
            ]
        )
        default_kwargs["memory"] = mock_memory
        default_kwargs["order"] = "Descending"

        component = component_class(**default_kwargs)
        result = await component.retrieve_messages()
        assert result[0].text == "Second"
        assert result[1].text == "First"
