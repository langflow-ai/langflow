import pytest
from langflow.components.vectorstores import QdrantVectorStoreComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestQdrantVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return QdrantVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "collection_name": "test_collection",
            "host": "localhost",
            "port": 6333,
            "grpc_port": 6334,
            "api_key": "test_api_key",
            "prefix": "test_prefix",
            "timeout": 30,
            "path": "/test/path",
            "url": "http://localhost",
            "distance_func": "Cosine",
            "content_payload_key": "page_content",
            "metadata_payload_key": "metadata",
            "number_of_results": 4,
            "embedding": Mock(spec=Embeddings),  # Mocking the Embeddings object
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "Qdrant"},
            {"version": "1.1.0", "module": "vectorstores", "file_name": "qdrant"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = component.build_vector_store()
        assert vector_store is not None
        assert isinstance(vector_store, Qdrant)

    async def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.search_query = "test query"
        component.ingest_data = [Mock(spec=Data)]  # Mocking the Data input
        results = component.search_documents()
        assert isinstance(results, list)
        assert len(results) <= default_kwargs["number_of_results"]
