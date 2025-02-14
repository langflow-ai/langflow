import pytest

from langflow.components.vectorstores import HCDVectorStoreComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestHCDVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return HCDVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "collection_name": "test_collection",
            "username": "hcd-superuser",
            "password": "HCD_PASSWORD",
            "api_endpoint": "HCD_API_ENDPOINT",
            "namespace": "default_namespace",
            "number_of_results": 4,
            "search_query": "example query",
            "search_type": "Similarity",
            "search_score_threshold": 0.5,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "HCDVectorStore"},
            {"version": "1.1.0", "module": "vectorstores", "file_name": "hcd_vector_store"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = component.build_vector_store()
        assert vector_store is not None, "Vector store should be initialized successfully."

    async def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.build_vector_store()  # Ensure vector store is built
        results = component.search_documents()
        assert isinstance(results, list), "Search documents should return a list."
        assert (
            len(results) <= default_kwargs["number_of_results"]
        ), "Should return up to the specified number of results."

    async def test_invalid_setup_mode(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.setup_mode = "InvalidMode"
        with pytest.raises(ValueError, match="Invalid setup mode: InvalidMode"):
            component.build_vector_store()
