import pytest

from langflow.components.memories import Mem0MemoryComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMem0MemoryComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return Mem0MemoryComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "mem0_config": {
                "graph_store": {
                    "provider": "neo4j",
                    "config": {"url": "neo4j+s://your-neo4j-url", "username": "neo4j", "password": "your-password"},
                },
                "version": "v1.1",
            },
            "ingest_message": "Hello, World!",
            "user_id": "user123",
            "search_query": "Hello",
            "mem0_api_key": "test_api_key",
            "metadata": {"key": "value"},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "memory", "file_name": "Mem0MemoryComponent"},
            {"version": "1.1.0", "module": "memory", "file_name": "Mem0MemoryComponent"},
        ]

    async def test_ingest_data(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = await component.ingest_data()

        # Assert
        assert result is not None
        assert default_kwargs["ingest_message"] in result.get_all(default_kwargs["user_id"])

    async def test_build_search_results(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = await component.build_search_results()

        # Assert
        assert result is not None
        assert isinstance(result, list)  # Assuming search results are returned as a list
        assert any(default_kwargs["ingest_message"] in memory for memory in result)
