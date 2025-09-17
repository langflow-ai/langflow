"""Tests for database-driven vector store factory."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from langflow.base.knowledge_bases.vector_store_factory import (
    ChromaVectorStoreAdapter,
    MockOpenSearchVectorStore,
    build_kb_vector_store,
)


class TestVectorStoreFactory:
    """Test the database-driven vector store factory."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def user_id(self):
        """Test user ID."""
        return uuid4()

    @pytest.fixture
    def kb_path(self):
        """Test knowledge base path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def mock_variable_service(self):
        """Mock variable service."""
        return AsyncMock()

    @pytest.mark.asyncio
    @patch("langflow.base.knowledge_bases.vector_store_factory.get_variable_service")
    async def test_build_chroma_store_default(
        self, mock_get_service, mock_variable_service, mock_session, user_id, kb_path
    ):
        """Test building Chroma store with default configuration (no variables)."""
        # Setup mocks
        mock_get_service.return_value = mock_variable_service
        mock_variable_service.get_by_category.return_value = []  # No KB variables

        with patch("langchain_chroma.Chroma") as mock_chroma:
            mock_chroma_instance = Mock()
            mock_chroma.return_value = mock_chroma_instance

            # Call factory
            result = await build_kb_vector_store(
                kb_path=kb_path,
                collection_name="test_collection",
                embedding_function=None,
                user_id=user_id,
                session=mock_session,
            )

            # Verify result
            assert isinstance(result, ChromaVectorStoreAdapter)
            assert result._store == mock_chroma_instance

            # Verify Chroma was called with correct parameters
            mock_chroma.assert_called_once_with(
                persist_directory=str(kb_path),
                collection_name="test_collection",
                embedding_function=None,
                client_settings=None,
            )

    @pytest.mark.asyncio
    @patch("langflow.base.knowledge_bases.vector_store_factory.get_variable_service")
    async def test_build_opensearch_store(
        self, mock_get_service, mock_variable_service, mock_session, user_id, kb_path
    ):
        """Test building OpenSearch store with configuration."""
        # Setup KB variables for OpenSearch
        mock_var1 = Mock()
        mock_var1.name = "kb_provider"
        mock_var1.value = "opensearch"

        mock_var2 = Mock()
        mock_var2.name = "kb_opensearch_url"
        mock_var2.value = "https://localhost:9200"

        mock_var3 = Mock()
        mock_var3.name = "kb_opensearch_index_prefix"
        mock_var3.value = "test-"

        mock_variables = [mock_var1, mock_var2, mock_var3]

        mock_get_service.return_value = mock_variable_service
        mock_variable_service.get_by_category.return_value = mock_variables

        # Call factory
        result = await build_kb_vector_store(
            kb_path=kb_path,
            collection_name="test_collection",
            embedding_function=None,
            user_id=user_id,
            session=mock_session,
        )

        # Verify result
        assert isinstance(result, MockOpenSearchVectorStore)
        assert result.opensearch_url == "https://localhost:9200"
        assert result.index_name == "test-test_collection"

    @pytest.mark.asyncio
    @patch("langflow.base.knowledge_bases.vector_store_factory.get_variable_service")
    async def test_build_chroma_with_server_config(
        self, mock_get_service, mock_variable_service, mock_session, user_id, kb_path
    ):
        """Test building Chroma store with server configuration."""
        # Setup KB variables for Chroma server
        mock_var1 = Mock()
        mock_var1.name = "kb_provider"
        mock_var1.value = "chroma"

        mock_var2 = Mock()
        mock_var2.name = "kb_chroma_server_host"
        mock_var2.value = "localhost"

        mock_var3 = Mock()
        mock_var3.name = "kb_chroma_server_http_port"
        mock_var3.value = "8000"

        mock_var4 = Mock()
        mock_var4.name = "kb_chroma_server_ssl_enabled"
        mock_var4.value = "true"

        mock_variables = [mock_var1, mock_var2, mock_var3, mock_var4]

        mock_get_service.return_value = mock_variable_service
        mock_variable_service.get_by_category.return_value = mock_variables

        with (
            patch("langchain_chroma.Chroma") as mock_chroma,
            patch("chromadb.HttpClient") as mock_http_client,
        ):
            mock_chroma_instance = Mock()
            mock_chroma.return_value = mock_chroma_instance
            mock_client_instance = Mock()
            mock_http_client.return_value = mock_client_instance

            # Call factory
            result = await build_kb_vector_store(
                kb_path=kb_path,
                collection_name="test_collection",
                embedding_function=None,
                user_id=user_id,
                session=mock_session,
            )

            # Verify result
            assert isinstance(result, ChromaVectorStoreAdapter)

            # Verify HttpClient was created with correct parameters
            mock_http_client.assert_called_once_with(
                host="localhost",
                port=8000,
                ssl=True,
            )

            # Verify Chroma was called with client
            mock_chroma.assert_called_once_with(
                client=mock_client_instance,
                collection_name="test_collection",
                embedding_function=None,
            )

    @pytest.mark.asyncio
    @patch("langflow.base.knowledge_bases.vector_store_factory.get_variable_service")
    async def test_unsupported_provider_raises_error(
        self, mock_get_service, mock_variable_service, mock_session, user_id, kb_path
    ):
        """Test that unsupported provider raises ValueError."""
        # Setup KB variables with unsupported provider
        mock_var1 = Mock()
        mock_var1.name = "kb_provider"
        mock_var1.value = "unsupported_provider"

        mock_variables = [mock_var1]

        mock_get_service.return_value = mock_variable_service
        mock_variable_service.get_by_category.return_value = mock_variables

        # Call factory and expect error
        with pytest.raises(ValueError, match="Unsupported vector store provider: unsupported_provider"):
            await build_kb_vector_store(
                kb_path=kb_path,
                collection_name="test_collection",
                embedding_function=None,
                user_id=user_id,
                session=mock_session,
            )

    @pytest.mark.asyncio
    @patch("langflow.base.knowledge_bases.vector_store_factory.get_variable_service")
    async def test_variable_service_called_correctly(
        self, mock_get_service, mock_variable_service, mock_session, user_id, kb_path
    ):
        """Test that variable service is called with correct parameters."""
        mock_get_service.return_value = mock_variable_service
        mock_variable_service.get_by_category.return_value = []

        with patch("langchain_chroma.Chroma"):
            await build_kb_vector_store(
                kb_path=kb_path,
                collection_name="test_collection",
                embedding_function=None,
                user_id=user_id,
                session=mock_session,
            )

            # Verify variable service was called correctly
            mock_get_service.assert_called_once()
            mock_variable_service.get_by_category.assert_called_once_with(user_id, "KB", mock_session)


class TestChromaVectorStoreAdapter:
    """Test ChromaVectorStoreAdapter."""

    @pytest.fixture
    def mock_chroma_store(self):
        """Mock LangChain Chroma store."""
        return Mock()

    @pytest.fixture
    def adapter(self, mock_chroma_store):
        """ChromaVectorStoreAdapter instance."""
        return ChromaVectorStoreAdapter(mock_chroma_store)

    def test_adapter_delegates_get(self, adapter, mock_chroma_store):
        """Test that adapter delegates get() to underlying store."""
        mock_chroma_store.get.return_value = {"documents": ["test"]}

        result = adapter.get(include=["documents"])

        assert result == {"documents": ["test"]}
        mock_chroma_store.get.assert_called_once_with(include=["documents"])

    def test_adapter_delegates_add_documents(self, adapter, mock_chroma_store):
        """Test that adapter delegates add_documents() to underlying store."""
        mock_documents = [Mock(), Mock()]
        mock_chroma_store.add_documents.return_value = ["id1", "id2"]

        result = adapter.add_documents(mock_documents)

        assert result == ["id1", "id2"]
        mock_chroma_store.add_documents.assert_called_once_with(mock_documents)

    def test_adapter_delegates_similarity_search(self, adapter, mock_chroma_store):
        """Test that adapter delegates similarity_search() to underlying store."""
        mock_results = [Mock(), Mock()]
        mock_chroma_store.similarity_search.return_value = mock_results

        result = adapter.similarity_search("test query", k=5)

        assert result == mock_results
        mock_chroma_store.similarity_search.assert_called_once_with("test query", k=5)

    def test_adapter_exposes_chroma_attributes(self, adapter, mock_chroma_store):
        """Test that adapter exposes Chroma-specific attributes."""
        mock_collection = Mock()
        mock_client = Mock()
        mock_chroma_store._collection = mock_collection
        mock_chroma_store._client = mock_client

        assert adapter._collection == mock_collection
        assert adapter._client == mock_client


class TestMockOpenSearchVectorStore:
    """Test MockOpenSearchVectorStore."""

    @pytest.fixture
    def mock_store(self):
        """MockOpenSearchVectorStore instance."""
        return MockOpenSearchVectorStore(opensearch_url="https://localhost:9200", index_name="test-index")

    def test_mock_store_initialization(self, mock_store):
        """Test mock store initializes correctly."""
        assert mock_store.opensearch_url == "https://localhost:9200"
        assert mock_store.index_name == "test-index"
        assert mock_store._documents == []

    def test_mock_store_add_documents(self, mock_store):
        """Test adding documents to mock store."""
        mock_doc1 = Mock()
        mock_doc1.page_content = "Document 1 content"
        mock_doc1.metadata = {"source": "doc1"}

        mock_doc2 = Mock()
        mock_doc2.page_content = "Document 2 content"
        mock_doc2.metadata = {"source": "doc2"}

        doc_ids = mock_store.add_documents([mock_doc1, mock_doc2])

        assert len(doc_ids) == 2
        assert doc_ids == ["doc_0", "doc_1"]
        assert len(mock_store._documents) == 2
        assert mock_store._documents[0]["content"] == "Document 1 content"
        assert mock_store._documents[1]["content"] == "Document 2 content"

    def test_mock_store_similarity_search(self, mock_store):
        """Test similarity search on mock store."""
        # Add some documents first
        mock_doc = Mock()
        mock_doc.page_content = "Test content"
        mock_doc.metadata = {"source": "test"}
        mock_store.add_documents([mock_doc])

        results = mock_store.similarity_search("query", k=1)

        assert len(results) == 1
        # Results should be Data objects
        assert hasattr(results[0], "data")

    def test_mock_store_get_method(self, mock_store):
        """Test get method on mock store."""
        # Add a document first
        mock_doc = Mock()
        mock_doc.page_content = "Test content"
        mock_doc.metadata = {"key": "value"}
        mock_store.add_documents([mock_doc])

        result = mock_store.get(include=["documents", "metadatas", "ids"])

        assert "documents" in result
        assert "metadatas" in result
        assert "ids" in result
        assert len(result["documents"]) == 1
        assert result["documents"][0] == "Test content"
        assert result["metadatas"][0] == {"key": "value"}
        assert result["ids"][0] == "doc_0"
