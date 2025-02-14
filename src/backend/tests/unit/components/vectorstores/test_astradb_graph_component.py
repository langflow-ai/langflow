import pytest

from langflow.components.vectorstores import AstraDBGraphVectorStoreComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAstraDBGraphVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AstraDBGraphVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "token": "test_token",
            "api_endpoint": "https://test.api.endpoint",
            "collection_name": "test_collection",
            "metadata_incoming_links_key": "test_key",
            "keyspace": "test_keyspace",
            "embedding_model": "test_model",
            "metric": "cosine",
            "batch_size": 10,
            "bulk_insert_batch_concurrency": 5,
            "bulk_insert_overwrite_concurrency": 3,
            "bulk_delete_concurrency": 2,
            "setup_mode": "Sync",
            "pre_delete_collection": False,
            "number_of_results": 4,
            "search_type": "Similarity",
            "search_score_threshold": 0.5,
            "search_filter": {"field": "value"},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "AstraDBGraph"},
            {"version": "1.1.0", "module": "vectorstores", "file_name": "AstraDBGraph"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = component.build_vector_store()
        assert vector_store is not None
        assert vector_store.collection_name == default_kwargs["collection_name"]

    async def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.search_query = "test query"
        results = component.search_documents()
        assert isinstance(results, list)
        assert len(results) <= default_kwargs["number_of_results"]

    async def test_invalid_setup_mode(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.setup_mode = "InvalidMode"
        with pytest.raises(ValueError, match="Invalid setup mode: InvalidMode"):
            component.build_vector_store()
