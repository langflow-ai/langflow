import pytest
from langflow.components.memories import AstraDBChatMemory
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAstraDBChatMemory(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AstraDBChatMemory

    @pytest.fixture
    def default_kwargs(self):
        return {
            "token": "test_token",
            "api_endpoint": "https://test.api.endpoint",
            "collection_name": "test_collection",
            "namespace": "test_namespace",
            "session_id": "test_session_id",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "memory", "file_name": "AstraDBChatMemory"},
        ]

    async def test_build_message_history(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        message_history = component.build_message_history()
        assert message_history is not None
        assert message_history.session_id == default_kwargs["session_id"]
        assert message_history.collection_name == default_kwargs["collection_name"]
        assert message_history.token == default_kwargs["token"]
        assert message_history.api_endpoint == default_kwargs["api_endpoint"]
        assert message_history.namespace == default_kwargs["namespace"]

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None
