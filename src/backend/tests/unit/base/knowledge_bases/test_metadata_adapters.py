"""Tests for enhanced metadata adapters."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from langflow.base.knowledge_bases.metadata_adapters import (
    ChromaMetadataAdapter,
    OpenSearchMetadataAdapter,
    create_metadata_adapter,
    extract_metadata,
)
from langflow.base.knowledge_bases.vector_store_factory import (
    ChromaVectorStoreAdapter,
    OpenSearchVectorStoreAdapter,
)


class TestMetadataAdapterCreation:
    """Test metadata adapter factory function."""

    def test_create_chroma_adapter(self):
        """Test creating Chroma metadata adapter."""
        # Create a mock LangChain Chroma store
        mock_langchain_store = Mock()
        mock_langchain_store.__class__.__name__ = "Chroma"

        # Wrap it in our adapter
        chroma_adapter = ChromaVectorStoreAdapter(mock_langchain_store)
        kb_path = Path("/test/kb")

        adapter = create_metadata_adapter(chroma_adapter, kb_path)

        assert isinstance(adapter, ChromaMetadataAdapter)
        assert adapter.vector_store is chroma_adapter
        assert adapter.kb_path == kb_path

    def test_create_opensearch_adapter(self):
        """Test creating OpenSearch metadata adapter."""
        # Create a mock that looks like an OpenSearchVectorStoreAdapter
        opensearch_store = OpenSearchVectorStoreAdapter(Mock(), "test-index")
        kb_path = Path("/test/kb")

        adapter = create_metadata_adapter(opensearch_store, kb_path)

        assert isinstance(adapter, OpenSearchMetadataAdapter)
        assert adapter.vector_store is opensearch_store
        assert adapter.kb_path == kb_path

    def test_create_mock_opensearch_adapter(self):
        """Test creating adapter for OpenSearch."""
        mock_opensearch_store = OpenSearchVectorStoreAdapter(Mock(), "test-index")
        kb_path = Path("/test/kb")

        adapter = create_metadata_adapter(mock_opensearch_store, kb_path)

        assert isinstance(adapter, OpenSearchMetadataAdapter)

    def test_unsupported_vector_store_raises_error(self):
        """Test that unsupported vector store raises ValueError."""
        unknown_store = Mock(spec=[])  # Empty spec means no attributes
        unknown_store.__class__.__name__ = "UnknownVectorStore"
        kb_path = Path("/test/kb")

        with pytest.raises(ValueError, match="Unsupported vector store type"):
            create_metadata_adapter(unknown_store, kb_path)


class TestChromaMetadataAdapter:
    """Test Chroma metadata adapter."""

    @pytest.fixture
    def mock_chroma_adapter(self):
        """Mock ChromaVectorStoreAdapter."""
        mock_langchain_store = Mock()
        mock_langchain_store.__class__.__name__ = "Chroma"
        return ChromaVectorStoreAdapter(mock_langchain_store)

    @pytest.fixture
    def adapter(self, mock_chroma_adapter):
        """ChromaMetadataAdapter instance."""
        kb_path = Path("/test/kb")
        return ChromaMetadataAdapter(mock_chroma_adapter, kb_path)

    def test_get_documents_and_metadata(self, adapter, mock_chroma_adapter):
        """Test getting documents and metadata."""
        mock_chroma_adapter._store.get.return_value = {
            "documents": ["doc1", "doc2"],
            "metadatas": [{"id": "1"}, {"id": "2"}],
        }

        result = adapter.get_documents_and_metadata()

        assert result["documents"] == ["doc1", "doc2"]
        assert result["metadatas"] == [{"id": "1"}, {"id": "2"}]
        mock_chroma_adapter._store.get.assert_called_once_with(include=["documents", "metadatas"])

    def test_get_document_count_with_collection(self, adapter, mock_chroma_adapter):
        """Test getting document count when collection is available."""
        mock_collection = Mock()
        mock_collection.count.return_value = 42
        mock_chroma_adapter._store._collection = mock_collection

        count = adapter.get_document_count()

        assert count == 42
        mock_collection.count.assert_called_once()

    def test_get_document_count_fallback(self, adapter, mock_chroma_adapter):
        """Test getting document count using fallback method."""
        mock_chroma_adapter._store._collection = None
        mock_chroma_adapter._store.get.return_value = {"documents": ["doc1", "doc2", "doc3"]}

        count = adapter.get_document_count()

        assert count == 3
        mock_chroma_adapter._store.get.assert_called_once()

    def test_get_collection_info(self, adapter, mock_chroma_adapter):
        """Test getting collection information."""
        mock_collection = Mock()
        mock_collection.name = "test_collection"
        mock_collection.count.return_value = 10
        mock_collection.metadata = {"version": "1.0"}
        mock_chroma_adapter._store._collection = mock_collection

        info = adapter.get_collection_info()

        assert info["name"] == "test_collection"
        assert info["count"] == 10
        assert info["metadata"] == {"version": "1.0"}

    def test_supports_embeddings_retrieval(self, adapter, mock_chroma_adapter):
        """Test embeddings retrieval support check."""
        mock_collection = Mock()
        mock_chroma_adapter._store._collection = mock_collection

        assert adapter.supports_embeddings_retrieval() is True

        mock_chroma_adapter._store._collection = None
        assert adapter.supports_embeddings_retrieval() is False

    def test_get_embeddings_for_documents(self, adapter, mock_chroma_adapter):
        """Test getting embeddings for specific documents."""
        mock_collection = Mock()
        mock_collection.get.return_value = {
            "metadatas": [{"_id": "doc1"}, {"_id": "doc2"}],
            "embeddings": [[0.1, 0.2], [0.3, 0.4]],
        }
        mock_chroma_adapter._store._collection = mock_collection

        embeddings = adapter.get_embeddings_for_documents(["doc1", "doc2"])

        assert embeddings["doc1"] == [0.1, 0.2]
        assert embeddings["doc2"] == [0.3, 0.4]
        mock_collection.get.assert_called_once()

    def test_get_provider_specific_metadata(self, adapter, mock_chroma_adapter):
        """Test getting Chroma-specific metadata."""
        mock_client = Mock()
        mock_client.get_version.return_value = "1.0.0"
        mock_chroma_adapter._store._client = mock_client

        metadata = adapter.get_provider_specific_metadata()

        assert metadata["provider"] == "chroma"
        assert metadata["client_type"] == "Mock"


class TestOpenSearchMetadataAdapter:
    """Test OpenSearch metadata adapter."""

    @pytest.fixture
    def mock_opensearch_store(self):
        """Mock OpenSearch vector store."""
        # Create a mock OpenSearch client and wrap it in the adapter
        mock_client = Mock()
        mock_client._index_name = "test-index"
        return OpenSearchVectorStoreAdapter(mock_client, "test-index")

    @pytest.fixture
    def adapter(self, mock_opensearch_store):
        """OpenSearchMetadataAdapter instance."""
        kb_path = Path("/test/kb")
        return OpenSearchMetadataAdapter(mock_opensearch_store, kb_path)

    def test_get_documents_and_metadata(self, adapter, mock_opensearch_store):
        """Test getting documents and metadata from OpenSearch."""
        # Add some test documents
        mock_doc = Mock()
        mock_doc.page_content = "Test content"
        mock_doc.metadata = {"source": "test"}
        mock_opensearch_store.add_documents([mock_doc])

        result = adapter.get_documents_and_metadata()

        assert "documents" in result
        assert "metadatas" in result
        assert len(result["documents"]) == 1
        assert result["documents"][0] == "Test content"

    def test_get_document_count(self, adapter, mock_opensearch_store):
        """Test getting document count from OpenSearch."""
        # Add some test documents
        mock_doc1 = Mock()
        mock_doc1.page_content = "Content 1"
        mock_doc1.metadata = {}
        mock_doc2 = Mock()
        mock_doc2.page_content = "Content 2"
        mock_doc2.metadata = {}
        mock_opensearch_store.add_documents([mock_doc1, mock_doc2])

        count = adapter.get_document_count()

        assert count == 2

    @pytest.mark.usefixtures("mock_opensearch_store")
    def test_get_collection_info(self, adapter):
        """Test getting OpenSearch collection information."""
        info = adapter.get_collection_info()

        assert info["index_name"] == "test-index"
        assert info["cluster_url"] == "https://localhost:9200"
        assert "document_count" in info

    def test_supports_embeddings_retrieval(self, adapter):
        """Test that OpenSearch mock doesn't support embeddings retrieval."""
        assert adapter.supports_embeddings_retrieval() is False

    def test_get_embeddings_for_documents(self, adapter):
        """Test that OpenSearch mock returns empty embeddings."""
        embeddings = adapter.get_embeddings_for_documents(["doc1", "doc2"])
        assert embeddings == {}

    @pytest.mark.usefixtures("mock_opensearch_store")
    def test_get_provider_specific_metadata(self, adapter):
        """Test getting OpenSearch-specific metadata."""
        metadata = adapter.get_provider_specific_metadata()

        assert metadata["provider"] == "opensearch"
        assert metadata["cluster_url"] == "https://localhost:9200"
        assert metadata["index_name"] == "test-index"


class TestExtractEnhancedMetadata:
    """Test enhanced metadata extraction."""

    def test_extract_metadata_chroma(self):
        """Test extracting metadata from Chroma vector store."""
        # Create mock Chroma adapter
        mock_langchain_store = Mock()
        mock_langchain_store.get.return_value = {
            "documents": ["Document 1", "Document 2"],
            "metadatas": [
                {"embedding_provider": "OpenAI", "embedding_model": "text-embedding-ada-002"},
                {"embedding_provider": "OpenAI", "embedding_model": "text-embedding-ada-002"},
            ],
        }
        mock_collection = Mock()
        mock_collection.count.return_value = 2
        mock_langchain_store._collection = mock_collection

        chroma_adapter = ChromaVectorStoreAdapter(mock_langchain_store)

        with tempfile.TemporaryDirectory() as temp_dir:
            kb_path = Path(temp_dir)

            metadata = extract_metadata(chroma_adapter, kb_path)

            assert metadata["chunks"] == 2
            assert metadata["words"] == 4  # "Document 1" + "Document 2" = 4 words
            assert metadata["characters"] == 20  # Total character count
            assert metadata["avg_chunk_size"] == 10.0  # 20 chars / 2 chunks
            assert metadata["embedding_provider"] == "OpenAI"
            assert metadata["embedding_model"] == "text-embedding-ada-002"
            assert metadata["provider"] == "chroma"
            assert metadata["supports_embeddings"] is True

    def test_extract_metadata_opensearch(self):
        """Test extracting metadata from OpenSearch vector store."""
        mock_client = Mock()
        mock_client._index_name = "test-index"
        opensearch_store = OpenSearchVectorStoreAdapter(mock_client, "test-index")

        # Mock the get method to return test data
        opensearch_store.get = Mock(
            return_value={
                "documents": ["Test document one", "Test document two"],
                "metadatas": [{"source": "test1"}, {"source": "test2"}],
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            kb_path = Path(temp_dir)

            metadata = extract_metadata(opensearch_store, kb_path)

            assert metadata["chunks"] == 2
            assert metadata["provider"] == "opensearch"
            assert metadata["supports_embeddings"] is False
            assert "collection_info" in metadata
            assert "provider_specific" in metadata

    def test_extract_metadata_empty_store(self):
        """Test extracting metadata from empty vector store."""
        mock_langchain_store = Mock()
        mock_langchain_store.get.return_value = {"documents": [], "metadatas": []}
        mock_collection = Mock()
        mock_collection.count.return_value = 0
        mock_langchain_store._collection = mock_collection

        chroma_adapter = ChromaVectorStoreAdapter(mock_langchain_store)

        with tempfile.TemporaryDirectory() as temp_dir:
            kb_path = Path(temp_dir)

            metadata = extract_metadata(chroma_adapter, kb_path)

            assert metadata["chunks"] == 0
            assert metadata["words"] == 0
            assert metadata["characters"] == 0
            assert metadata["avg_chunk_size"] == 0.0
            assert metadata["embedding_provider"] == "Unknown"
            assert metadata["embedding_model"] == "Unknown"

    def test_extract_metadata_error_handling(self):
        """Test error handling in metadata extraction."""
        # Create a mock that raises an exception
        mock_langchain_store = Mock()
        mock_langchain_store.get.side_effect = Exception("Test error")

        chroma_adapter = ChromaVectorStoreAdapter(mock_langchain_store)

        with tempfile.TemporaryDirectory() as temp_dir:
            kb_path = Path(temp_dir)

            metadata = extract_metadata(chroma_adapter, kb_path)

            # Should return minimal metadata on error
            assert metadata["chunks"] == 0
            assert metadata["embedding_provider"] == "Unknown"
            assert metadata["provider"] == "unknown"  # Error in adapter returns unknown provider

    def test_extract_metadata_with_schema_data(self):
        """Test extracting metadata with schema data provided."""
        mock_langchain_store = Mock()
        mock_langchain_store.get.return_value = {"documents": ["Test document"], "metadatas": [{"source": "test"}]}
        mock_collection = Mock()
        mock_collection.count.return_value = 1
        mock_langchain_store._collection = mock_collection

        chroma_adapter = ChromaVectorStoreAdapter(mock_langchain_store)

        schema_data = [{"column_name": "text", "vectorize": True}, {"column_name": "metadata", "vectorize": False}]

        with tempfile.TemporaryDirectory() as temp_dir:
            kb_path = Path(temp_dir)

            metadata = extract_metadata(chroma_adapter, kb_path, schema_data=schema_data)

            assert metadata["chunks"] == 1
            assert metadata["provider"] == "chroma"
