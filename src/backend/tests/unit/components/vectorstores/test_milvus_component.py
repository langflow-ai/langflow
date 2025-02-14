import pytest
from langflow.components.vectorstores import MilvusVectorStoreComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMilvusVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MilvusVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "collection_name": "test_collection",
            "uri": "http://localhost:19530",
            "password": "",
            "primary_field": "pk",
            "text_field": "text",
            "vector_field": "vector",
            "number_of_results": 4,
            "ingest_data": [],
            "search_query": "example query",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "Milvus"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = component.build_vector_store()
        assert vector_store is not None
        assert vector_store.collection_name == default_kwargs["collection_name"]

    async def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.ingest_data = ["Document 1", "Document 2"]
        component.build_vector_store()  # Build the vector store with documents
        results = component.search_documents()
        assert isinstance(results, list)
        assert len(results) <= default_kwargs["number_of_results"]
