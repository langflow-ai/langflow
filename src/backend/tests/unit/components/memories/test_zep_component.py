import pytest

from langflow.components.memories import ZepChatMemory
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestZepChatMemory(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ZepChatMemory

    @pytest.fixture
    def default_kwargs(self):
        return {
            "url": "http://example.com",
            "api_key": "test_api_key",
            "api_base_path": "api/v1",
            "session_id": "test_session_id",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "memory", "file_name": "ZepChatMemory"},
        ]

    async def test_build_message_history(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        message_history = component.build_message_history()
        assert message_history is not None
        assert hasattr(message_history, "session_id")
        assert message_history.session_id == default_kwargs["session_id"]

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None
