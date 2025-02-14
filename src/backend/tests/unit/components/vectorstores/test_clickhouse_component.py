import pytest

from langflow.components.vectorstores import ClickhouseVectorStoreComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestClickhouseVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ClickhouseVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "host": "localhost",
            "port": 8123,
            "database": "test_db",
            "table": "test_table",
            "username": "user",
            "password": "password",
            "index_type": "annoy",
            "metric": "euclidean",
            "number_of_results": 5,
            "score_threshold": 0.5,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "ClickhouseVectorStoreComponent"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = await component.build_vector_store()
        assert vector_store is not None

    async def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.ingest_data = ["Sample document 1", "Sample document 2"]
        component.search_query = "Sample"
        results = await component.search_documents()
        assert isinstance(results, list)
        assert len(results) <= default_kwargs["number_of_results"]

    async def test_failed_connection(self, component_class):
        component = component_class(host="invalid_host", port=9999, username="user", password="password")
        with pytest.raises(ValueError, match="Failed to connect to Clickhouse"):
            await component.build_vector_store()
