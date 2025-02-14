import pytest

from langflow.components.vectorstores import AstraDBVectorStoreComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAstraDBVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AstraDBVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "token": "test_token",
            "environment": "test_env",
            "api_endpoint": "test_api_endpoint",
            "collection_name": "test_collection",
            "number_of_results": 5,
            "search_type": "Similarity",
            "search_query": "test query",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "astradb_vectorstore", "file_name": "AstraDBVectorStore"},
        ]

    def test_post_code_processing(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]
        assert node_data["token"]["value"] == "test_token"
        assert node_data["environment"]["value"] == "test_env"
        assert node_data["api_endpoint"]["value"] == "test_api_endpoint"
        assert node_data["collection_name"]["value"] == "test_collection"
        assert node_data["number_of_results"]["value"] == 5
        assert node_data["search_type"]["value"] == "Similarity"
        assert node_data["search_query"]["value"] == "test query"

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = await component.build_vector_store()
        assert vector_store is not None

    async def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        results = await component.search_documents()
        assert isinstance(results, list)
