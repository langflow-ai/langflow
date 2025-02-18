import pytest
from langflow.components.vectorstores import OpenSearchVectorStoreComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestOpenSearchVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return OpenSearchVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "opensearch_url": "http://localhost:9200",
            "index_name": "langflow",
            "embedding": "dummy_embedding_function",
            "search_type": "similarity",
            "number_of_results": 4,
            "search_score_threshold": 0.0,
            "username": "admin",
            "password": "admin",
            "use_ssl": True,
            "verify_certs": False,
            "hybrid_search_query": "",
            "ingest_data": [],
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "OpenSearchVectorStore"},
            {"version": "1.1.0", "module": "vectorstores", "file_name": "OpenSearchVectorStore"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = component.build_vector_store()
        assert vector_store is not None
        assert vector_store.index_name == default_kwargs["index_name"]

    async def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        results = await component.search_documents()
        assert isinstance(results, list)

    async def test_invalid_hybrid_search_query(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.hybrid_search_query = "{invalid_json}"
        with pytest.raises(ValueError, match="Invalid hybrid search query JSON"):
            await component.search("test query")

    async def test_search_with_no_query(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        results = await component.search(None)
        assert isinstance(results, list)

    async def test_search_with_invalid_type(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.search_type = "invalid_type"
        with pytest.raises(ValueError, match="Error during search. Invalid search type"):
            await component.search("test query")
