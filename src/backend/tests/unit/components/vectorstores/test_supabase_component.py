import pytest
from langflow.components.vectorstores import SupabaseVectorStoreComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSupabaseVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SupabaseVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "supabase_url": "https://example.supabase.co",
            "supabase_service_key": "your_service_key",
            "table_name": "documents",
            "query_name": "search_query",
            "embedding": "your_embedding",
            "number_of_results": 4,
            "ingest_data": [],
            "search_query": "example search",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "SupabaseVectorStore"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        vector_store = component.build_vector_store()
        assert vector_store is not None
        assert isinstance(vector_store, SupabaseVectorStore)

    async def test_search_documents_with_results(self, component_class, default_kwargs):
        default_kwargs["ingest_data"] = ["Document 1", "Document 2"]
        component = await self.component_setup(component_class, default_kwargs)
        results = component.search_documents()
        assert isinstance(results, list)
        assert len(results) <= default_kwargs["number_of_results"]

    async def test_search_documents_no_query(self, component_class, default_kwargs):
        default_kwargs["search_query"] = ""
        component = await self.component_setup(component_class, default_kwargs)
        results = component.search_documents()
        assert results == []
