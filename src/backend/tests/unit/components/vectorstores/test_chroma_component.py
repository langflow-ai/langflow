import pytest

from langflow.components.vectorstores import ChromaVectorStoreComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestChromaVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ChromaVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "collection_name": "test_collection",
            "persist_directory": "/path/to/persist",
            "embedding": "test_embedding_function",
            "chroma_server_host": "localhost",
            "chroma_server_http_port": 8000,
            "chroma_server_grpc_port": 8001,
            "chroma_server_ssl_enabled": False,
            "allow_duplicates": True,
            "search_type": "Similarity",
            "number_of_results": 5,
            "limit": 10,
            "ingest_data": [],  # Add test data if needed
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "ChromaVectorStore"},
            {"version": "1.1.0", "module": "vectorstores", "file_name": "chroma_vector_store"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = await component.build_vector_store()
        assert vector_store is not None
        assert vector_store.collection_name == default_kwargs["collection_name"]

    async def test_add_documents_to_vector_store(self, component_class, default_kwargs):
        default_kwargs["ingest_data"] = [Data(text="Test document 1"), Data(text="Test document 2")]
        component = component_class(**default_kwargs)
        vector_store = await component.build_vector_store()
        await component._add_documents_to_vector_store(vector_store)
        # Assuming the vector store has a method to get documents
        stored_documents = vector_store.get(limit=default_kwargs["limit"])
        assert len(stored_documents) == 2  # Check if documents were added
        assert stored_documents[0].text == "Test document 1"
        assert stored_documents[1].text == "Test document 2"

    async def test_no_duplicates_when_allow_duplicates_false(self, component_class, default_kwargs):
        default_kwargs["allow_duplicates"] = False
        default_kwargs["ingest_data"] = [Data(text="Test document 1"), Data(text="Test document 1")]
        component = component_class(**default_kwargs)
        vector_store = await component.build_vector_store()
        await component._add_documents_to_vector_store(vector_store)
        stored_documents = vector_store.get(limit=default_kwargs["limit"])
        assert len(stored_documents) == 1  # Only one document should be stored
        assert stored_documents[0].text == "Test document 1"

    async def test_invalid_input_type(self, component_class, default_kwargs):
        default_kwargs["ingest_data"] = ["Invalid input"]  # Not a Data object
        component = component_class(**default_kwargs)
        vector_store = await component.build_vector_store()
        with pytest.raises(TypeError, match="Vector Store Inputs must be Data objects."):
            await component._add_documents_to_vector_store(vector_store)
