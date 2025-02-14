import pytest

from langflow.components.vectorstores import CouchbaseVectorStoreComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCouchbaseVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CouchbaseVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "couchbase_connection_string": "couchbase://localhost",
            "couchbase_username": "username",
            "couchbase_password": "password",
            "bucket_name": "test_bucket",
            "scope_name": "test_scope",
            "collection_name": "test_collection",
            "index_name": "test_index",
            "embedding": "test_embedding",
            "number_of_results": 4,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "CouchbaseVectorStore"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = await component.build_vector_store()
        assert vector_store is not None, "Vector store should not be None."
        assert isinstance(vector_store, CouchbaseVectorStore), "Should return an instance of CouchbaseVectorStore."

    async def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.search_query = "example query"
        results = await component.search_documents()
        assert isinstance(results, list), "Search results should be a list."
