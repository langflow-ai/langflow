import pytest

from langflow.components.vectorstores import RedisVectorStoreComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestRedisVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return RedisVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "redis_server_url": "redis://localhost:6379",
            "redis_index_name": "test_index",
            "number_of_results": 4,
            "embedding": "test_embedding",
            "schema": None,
            "ingest_data": [],
            "search_query": "example query",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "RedisVectorStoreComponent"},
        ]

    async def test_build_vector_store_with_no_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="If no documents are provided, a schema must be provided."):
            await component.build_vector_store()

    async def test_build_vector_store_with_documents(self, component_class, default_kwargs):
        default_kwargs["ingest_data"] = ["Document 1", "Document 2"]
        component = component_class(**default_kwargs)
        vector_store = await component.build_vector_store()
        assert vector_store is not None

    async def test_search_documents(self, component_class, default_kwargs):
        default_kwargs["ingest_data"] = ["Document 1", "Document 2"]
        component = component_class(**default_kwargs)
        await component.build_vector_store()
        results = await component.search_documents()
        assert isinstance(results, list)
        assert len(results) <= default_kwargs["number_of_results"]

    async def test_search_documents_with_empty_query(self, component_class, default_kwargs):
        default_kwargs["ingest_data"] = ["Document 1", "Document 2"]
        default_kwargs["search_query"] = ""
        component = component_class(**default_kwargs)
        await component.build_vector_store()
        results = await component.search_documents()
        assert results == []
