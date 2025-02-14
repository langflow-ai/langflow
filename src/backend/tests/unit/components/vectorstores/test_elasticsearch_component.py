import pytest
from langflow.components.vectorstores import ElasticsearchVectorStoreComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestElasticsearchVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ElasticsearchVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "elasticsearch_url": "http://localhost:9200",
            "index_name": "langflow",
            "username": "elastic",
            "password": "password",
            "number_of_results": 4,
            "search_score_threshold": 0.0,
            "search_type": "similarity",
            "ingest_data": [],
            "_session_id": "123",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "ElasticsearchVectorStoreComponent"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = component.build_vector_store()
        assert vector_store is not None

    async def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.ingest_data = []  # Assuming no documents to ingest for this test
        results = component.search_documents()
        assert results == []

    async def test_invalid_search_type(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.search_type = "invalid_type"
        with pytest.raises(ValueError, match="Invalid search type: invalid_type"):
            component.search("test query")

    async def test_get_all_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = component.build_vector_store()
        results = component.get_all_documents(vector_store)
        assert isinstance(results, list)

    async def test_prepare_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.ingest_data = []  # Assuming no documents to prepare
        documents = component._prepare_documents()
        assert documents == []
