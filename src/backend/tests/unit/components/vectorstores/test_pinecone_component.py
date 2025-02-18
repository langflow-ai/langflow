import pytest
from langflow.components.vectorstores import PineconeVectorStoreComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestPineconeVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return PineconeVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "index_name": "test_index",
            "namespace": "test_namespace",
            "distance_strategy": "Cosine",
            "pinecone_api_key": "test_api_key",
            "text_key": "text",
            "number_of_results": 4,
            "ingest_data": [],
            "search_query": "example query",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "Pinecone"},
            {"version": "1.1.0", "module": "vectorstores", "file_name": "pinecone"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = await component.build_vector_store()
        assert vector_store is not None
        assert vector_store.index_name == default_kwargs["index_name"]

    async def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.build_vector_store = pytest.AsyncMock(return_value=component.build_vector_store())
        component.search_query = "example query"
        results = await component.search_documents()
        assert isinstance(results, list)
        assert component.status is not None
