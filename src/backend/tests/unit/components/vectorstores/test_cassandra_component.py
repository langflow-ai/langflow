import pytest
from langflow.components.vectorstores import CassandraVectorStoreComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCassandraVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CassandraVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "database_ref": "test_database",
            "username": "test_user",
            "token": "test_token",
            "keyspace": "test_keyspace",
            "table_name": "test_table",
            "ttl_seconds": 3600,
            "batch_size": 16,
            "setup_mode": "Sync",
            "embedding": "test_embedding",
            "number_of_results": 4,
            "search_type": "Similarity",
            "search_score_threshold": 0.5,
            "search_filter": {},
            "body_search": "test body search",
            "enable_body_search": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "Cassandra"},
            {"version": "1.1.0", "module": "vectorstores", "file_name": "cassandra"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = await component.build_vector_store()
        assert vector_store is not None
        assert vector_store.table_name == default_kwargs["table_name"]
        assert vector_store.keyspace == default_kwargs["keyspace"]

    async def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.search_query = "test search query"
        results = await component.search_documents()
        assert isinstance(results, list)
        assert len(results) <= default_kwargs["number_of_results"]

    async def test_invalid_search_filter(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.search_query = "test search query"
        component.search_filter = {"invalid_key": None}
        with pytest.raises(ValueError, match="You should ingest data through Langflow"):
            await component.search_documents()
