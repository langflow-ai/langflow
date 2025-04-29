import pytest
from langflow.components.memories import RedisIndexChatMemory
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestRedisIndexChatMemory(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return RedisIndexChatMemory

    @pytest.fixture
    def default_kwargs(self):
        return {
            "host": "localhost",
            "port": 6379,
            "database": "0",
            "username": "user",
            "password": "pass",
            "key_prefix": "test_",
            "session_id": "session_123",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_build_message_history(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        message_history = component.build_message_history()

        # Assert
        assert message_history is not None
        assert message_history.session_id == default_kwargs["session_id"]
        assert message_history.url == "redis://user:pass@localhost:6379/0"
        assert message_history.key_prefix == default_kwargs["key_prefix"]

    def test_missing_required_fields(self, component_class):
        # Arrange
        component = component_class()

        # Act & Assert
        with pytest.raises(ValueError):
            component.build_message_history()
