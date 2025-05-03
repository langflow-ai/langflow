import pytest
from langflow.components.vectorstores import PGVectorStoreComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestPGVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return PGVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "pg_server_url": "postgresql://user:password@localhost:5432/mydatabase",
            "collection_name": "my_collection",
            "embedding": "my_embedding",
            "number_of_results": 4,
            "search_query": "example query",
            "ingest_data": [],
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "PGVectorStore"},
        ]

    async def test_build_vector_store_with_documents(self, component_class, default_kwargs):
        default_kwargs["ingest_data"] = ["doc1", "doc2"]
        component = await self.component_setup(component_class, default_kwargs)
        vector_store = component.build_vector_store()
        assert vector_store is not None

    async def test_build_vector_store_with_existing_index(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        vector_store = component.build_vector_store()
        assert vector_store is not None

    async def test_search_documents(self, component_class, default_kwargs):
        default_kwargs["ingest_data"] = ["doc1", "doc2"]
        component = await self.component_setup(component_class, default_kwargs)
        component.build_vector_store()  # Ensure the vector store is built
        results = component.search_documents()
        assert isinstance(results, list)

    async def test_search_documents_no_query(self, component_class, default_kwargs):
        default_kwargs["search_query"] = ""
        component = await self.component_setup(component_class, default_kwargs)
        results = component.search_documents()
        assert results == []
