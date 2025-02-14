import pytest

from langflow.components.vectorstores import CassandraGraphVectorStoreComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCassandraGraphVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CassandraGraphVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "database_ref": "test_database_id",
            "username": "test_user",
            "token": "test_token",
            "keyspace": "test_keyspace",
            "table_name": "test_table",
            "setup_mode": "Sync",
            "embedding": "test_embedding",
            "number_of_results": 4,
            "search_type": "Traversal",
            "depth": 1,
            "search_score_threshold": 0.0,
            "search_filter": {},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "CassandraGraph"},
            {"version": "1.1.0", "module": "vectorstores", "file_name": "cassandra_graph"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = await component.build_vector_store()
        assert vector_store is not None
        assert vector_store.node_table == default_kwargs["table_name"]
        assert vector_store.keyspace == default_kwargs["keyspace"]

    async def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.search_query = "test query"
        results = await component.search_documents()
        assert isinstance(results, list)
        assert len(results) <= default_kwargs["number_of_results"]

    async def test_invalid_database_ref(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.database_ref = "invalid_ref"
        with pytest.raises(ValueError, match="You should ingest data through Langflow"):
            await component.search_documents()
