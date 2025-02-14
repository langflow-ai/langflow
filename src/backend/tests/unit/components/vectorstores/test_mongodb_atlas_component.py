import pytest
from langflow.components.vectorstores import MongoVectorStoreComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMongoVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MongoVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "mongodb_atlas_cluster_uri": "mongodb+srv://user:password@cluster.mongodb.net/test",
            "enable_mtls": False,
            "db_name": "test_db",
            "collection_name": "test_collection",
            "index_name": "test_index",
            "embedding": "dummy_embedding",
            "number_of_results": 4,
            "ingest_data": [],
            "search_query": "test query",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "MongoVectorStore"},
            {"version": "1.1.0", "module": "vectorstores", "file_name": "mongo_vector_store"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = component.build_vector_store()
        assert vector_store is not None
        assert vector_store.collection.name == default_kwargs["collection_name"]

    async def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.ingest_data = ["Sample document 1", "Sample document 2"]
        vector_store = component.build_vector_store()
        results = component.search_documents()
        assert isinstance(results, list)
        assert len(results) <= default_kwargs["number_of_results"]

    async def test_search_documents_no_query(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.search_query = None
        results = component.search_documents()
        assert results == []
