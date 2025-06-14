import uuid
from unittest.mock import Mock, patch

import pytest
from base.langflow.components.gridgain import GridGainVectorStoreComponent
from langchain.schema import Document
from pygridgain import Client


class MockData:
    def __init__(self, content, metadata=None):
        self.content = content
        self.metadata = metadata or {}

    def to_lc_document(self):
        return Document(page_content=self.content, metadata=self.metadata)


@pytest.fixture
def mock_client():
    return Mock(spec=["connect"])


@pytest.fixture
def mock_embedding():
    return Mock()


@pytest.fixture
def component():
    return GridGainVectorStoreComponent()


@pytest.fixture
def sample_data():
    return MockData(
        content="Test content",
        metadata={
            "id": str(uuid.uuid4()),
            "vector_id": str(uuid.uuid4()),
            "url": "http://example.com",
            "title": "Test Document",
        },
    )


class TestGridGainVectorStoreComponent:
    """Test cases for GridGainVectorStoreComponent."""

    def test_process_data_input_with_valid_data(self, component, sample_data):
        # Test processing valid data input
        result = component._process_data_input(sample_data)

        assert isinstance(result, Document)
        assert result.page_content == "Test content"
        assert isinstance(result.metadata, dict)
        assert all(key in result.metadata for key in ["id", "vector_id", "url", "title"])
        assert isinstance(result.metadata["id"], str)
        assert isinstance(result.metadata["vector_id"], str)

    def test_process_data_input_with_missing_metadata(self, component):
        # Test processing data with minimal metadata
        data = MockData(content="Test content", metadata={})
        result = component._process_data_input(data)

        assert isinstance(result, Document)
        assert result.page_content == "Test content"
        assert isinstance(result.metadata["id"], str)
        assert isinstance(result.metadata["vector_id"], str)
        assert result.metadata["url"] == ""
        assert result.metadata["title"] == ""

    def test_build_vector_store(self, component: GridGainVectorStoreComponent, mock_embedding):
        # Configure component
        component.host = "localhost"
        component.port = 10800
        component.cache_name = "test_cache"
        component.embedding = mock_embedding
        component.ingest_data = []  # Empty list for this test

        # Create mock client
        client = Client()

        # Mock the Client class
        with patch("pygridgain.Client", return_value=mock_client):
            vector_store = component.build_vector_store()

            client.connect(component.host, component.port)
            assert vector_store is not None

    def test_search_documents(self, component):
        # Configure component
        component.search_query = "test query"
        component.number_of_results = 4
        component.score_threshold = 0.6

        # Mock vector store and its similarity_search method
        mock_vector_store = Mock()
        mock_docs = [
            Document(page_content="Result 1", metadata={"id": "1"}),
            Document(page_content="Result 2", metadata={"id": "2"}),
        ]
        mock_vector_store.similarity_search.return_value = mock_docs

        with patch.object(component, "build_vector_store", return_value=mock_vector_store):
            results = component.search_documents()

            assert len(results) == 2
            mock_vector_store.similarity_search.assert_called_once_with(query="test query", k=4, score_threshold=0.6)
