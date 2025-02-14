import pytest

from langflow.components.vectorstores import UpstashVectorStoreComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestUpstashVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return UpstashVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "index_url": "https://example.upstash.io",
            "index_token": "secret_token",
            "text_key": "text",
            "namespace": "default",
            "number_of_results": 4,
            "ingest_data": [],
            "search_query": "example query",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "UpstashVectorStore"},
        ]

    async def test_build_vector_store_with_documents(self, component_class, default_kwargs):
        default_kwargs["ingest_data"] = ["Document 1", "Document 2"]
        component = component_class(**default_kwargs)
        vector_store = await component.build_vector_store()
        assert vector_store is not None
        assert len(vector_store.documents) == 2

    async def test_build_vector_store_without_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = await component.build_vector_store()
        assert vector_store is not None
        assert len(vector_store.documents) == 0

    async def test_search_documents(self, component_class, default_kwargs):
        default_kwargs["ingest_data"] = ["Document 1", "Document 2"]
        component = component_class(**default_kwargs)
        await component.build_vector_store()
        results = await component.search_documents()
        assert results is not None
        assert isinstance(results, list)

    async def test_search_documents_no_query(self, component_class, default_kwargs):
        default_kwargs["ingest_data"] = ["Document 1", "Document 2"]
        default_kwargs["search_query"] = ""
        component = component_class(**default_kwargs)
        await component.build_vector_store()
        results = await component.search_documents()
        assert results == []
