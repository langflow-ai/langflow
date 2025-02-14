import pytest

from langflow.components.vectorstores import WeaviateVectorStoreComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestWeaviateVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return WeaviateVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "url": "http://localhost:8080",
            "api_key": None,
            "index_name": "TestIndex",
            "text_key": "text",
            "embedding": None,
            "number_of_results": 4,
            "search_by_text": True,
            "ingest_data": [],
            "search_query": "example query",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "WeaviateVectorStoreComponent"},
        ]

    def test_build_vector_store_with_api_key(self, component_class, default_kwargs):
        default_kwargs["api_key"] = "test_api_key"
        component = component_class(**default_kwargs)
        vector_store = component.build_vector_store()
        assert vector_store is not None

    def test_build_vector_store_without_api_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = component.build_vector_store()
        assert vector_store is not None

    def test_capitalized_index_name(self, component_class, default_kwargs):
        default_kwargs["index_name"] = "testindex"
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Weaviate requires the index name to be capitalized"):
            component.build_vector_store()

    def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.build_vector_store = lambda: Mock()  # Mocking the build_vector_store method
        component.search_query = "example query"
        component.search_documents()
        assert component.status is not None
