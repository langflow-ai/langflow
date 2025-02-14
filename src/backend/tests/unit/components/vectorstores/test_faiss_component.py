import pytest

from langflow.components.vectorstores import FaissVectorStoreComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestFaissVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return FaissVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "index_name": "test_index",
            "persist_directory": "./faiss_index",
            "embedding": "test_embedding",
            "number_of_results": 5,
            "allow_dangerous_deserialization": True,
            "ingest_data": [],
            "search_query": "example query",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "FaissVectorStoreComponent"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Folder path is required to save the FAISS index."):
            await component.build_vector_store()

        # Set ingest_data to a valid input for the test
        default_kwargs["ingest_data"] = ["document1", "document2"]
        component = component_class(**default_kwargs)
        result = await component.build_vector_store()
        assert result is not None

    async def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Folder path is required to load the FAISS index."):
            await component.search_documents()

        # Set persist_directory and ingest_data for the test
        default_kwargs["persist_directory"] = "./faiss_index"
        default_kwargs["ingest_data"] = ["document1", "document2"]
        component = component_class(**default_kwargs)
        await component.build_vector_store()  # Build the vector store first

        results = await component.search_documents()
        assert isinstance(results, list)
        assert len(results) <= default_kwargs["number_of_results"]

    async def test_invalid_search_query(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        default_kwargs["search_query"] = ""
        component = component_class(**default_kwargs)
        results = await component.search_documents()
        assert results == []
