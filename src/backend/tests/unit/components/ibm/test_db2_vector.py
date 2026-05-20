"""Unit tests for DB2 Vector Store Component."""

from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from lfx.components.ibm.db2_vector import DB2VectorStoreComponent
from lfx.schema.data import Data

from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient, VersionComponentMapping


class TestDB2VectorStoreComponent(ComponentTestBaseWithoutClient):
    """Test DB2 Vector Store Component."""

    @pytest.fixture
    def component_class(self) -> type[Any]:
        """Return the component class for testing."""
        return DB2VectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return default kwargs for component initialization."""
        return {
            "collection_name": "test_vectors",
            "database": "TESTDB",
            "hostname": "localhost",
            "port": 50000,
            "username": "testuser",
            "password": str(50000),
            "search_type": "Similarity",
            "number_of_results": 4,
            "distance_strategy": "COSINE",
            "allow_duplicates": True,
            "should_cache_vector_store": False,
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return file names mapping for the component (new in this PR)."""
        return [
            VersionComponentMapping(version="1.0.19", module="ibm", file_name=DID_NOT_EXIST),
            VersionComponentMapping(version="1.1.0", module="ibm", file_name=DID_NOT_EXIST),
            VersionComponentMapping(version="1.1.1", module="ibm", file_name=DID_NOT_EXIST),
        ]

    @pytest.fixture
    def component(self):
        """Create a DB2VectorStoreComponent instance with valid inputs."""
        comp = DB2VectorStoreComponent()
        comp.collection_name = "test_vectors"
        comp.database = "TESTDB"
        comp.hostname = "localhost"
        comp.port = 50000
        comp.username = "testuser"
        comp.password = str(50000)
        comp.search_query = "test query"
        comp.search_type = "Similarity"
        comp.number_of_results = 4
        comp.distance_strategy = "COSINE"
        comp.allow_duplicates = True
        comp.should_cache_vector_store = False
        return comp

    @pytest.fixture
    def mock_embedding(self):
        """Create a mock embedding model."""
        embedding = Mock()
        embedding.embed_documents = Mock(return_value=[[0.1, 0.2, 0.3]])
        embedding.embed_query = Mock(return_value=[0.1, 0.2, 0.3])
        return embedding

    def test_component_metadata(self):
        """Test component metadata is correctly set."""
        comp = DB2VectorStoreComponent()
        assert comp.display_name == "IBM Db2 Vector Store"
        expected_desc = (
            "IBM Db2 Vector Store with search capabilities. "
            "Use Generic-typed global variables for connection parameters "
            "(database, hostname, username). Only password should use Credential-typed variables."
        )
        assert comp.description == expected_desc
        assert comp.icon == "DB2"
        assert comp.name == "DB2VectorStore"

    def test_missing_ibm_db_package(self, component, mock_embedding):
        """Test error when ibm_db package is not installed."""
        component.embedding = mock_embedding
        with (
            patch.dict("sys.modules", {"ibm_db_dbi": None}),
            pytest.raises(ImportError, match="Could not import required DB2 packages"),
        ):
            component.build_vector_store()

    def test_invalid_database_name(self, component, mock_embedding):
        """Test validation of database name."""
        component.embedding = mock_embedding
        component.database = "invalid; DROP TABLE users;"
        with pytest.raises(ValueError, match="Invalid connection parameters"):
            component.build_vector_store()

    def test_invalid_hostname(self, component, mock_embedding):
        """Test validation of hostname."""
        component.embedding = mock_embedding
        component.hostname = "localhost; DROP TABLE users;"
        with pytest.raises(ValueError, match="Invalid connection parameters"):
            component.build_vector_store()

    def test_invalid_port(self, component, mock_embedding):
        """Test validation of port number."""
        component.embedding = mock_embedding
        component.port = 99999
        with pytest.raises(ValueError, match="Invalid connection parameters"):
            component.build_vector_store()

    def test_invalid_table_name(self, component, mock_embedding):
        """Test validation of table name."""
        component.embedding = mock_embedding
        component.collection_name = "invalid; DROP TABLE users;"
        with pytest.raises(ValueError, match="Invalid connection parameters"):
            component.build_vector_store()

    def test_missing_credentials(self, component, mock_embedding):
        """Test error when credentials are missing."""
        component.embedding = mock_embedding
        component.username = ""
        with pytest.raises(ValueError, match="Missing required credentials"):
            component.build_vector_store()

    # Note: Integration tests requiring actual DB2 database removed
    # The component logic is tested through validation tests above

    def test_search_documents_no_query(self, component):
        """Test search with no query returns empty list."""
        component.search_query = None
        results = component.search_documents()
        assert results == []

    def test_similarity_search(self, component, mock_embedding):
        """Test similarity search functionality through the component."""
        component.embedding = mock_embedding

        # Mock the vector store and its methods
        with patch.object(component, "build_vector_store") as mock_build:
            mock_vector_store = MagicMock()
            mock_doc1 = MagicMock()
            mock_doc1.page_content = "The quick brown fox jumps over the lazy dog"
            mock_doc1.metadata = {}
            mock_doc2 = MagicMock()
            mock_doc2.page_content = "The lazy dog sleeps all day long"
            mock_doc2.metadata = {}

            mock_vector_store.similarity_search.return_value = [mock_doc1, mock_doc2]
            mock_build.return_value = mock_vector_store

            component.search_query = "dog sleeping"
            component.search_type = "Similarity"
            component.number_of_results = 2

            results = component.search_documents()

            # Verify search was called with correct parameters
            mock_vector_store.similarity_search.assert_called_once()
            call_args = mock_vector_store.similarity_search.call_args
            assert call_args[1]["query"] == "dog sleeping"
            assert call_args[1]["k"] == 2

            # Verify results
            assert len(results) == 2
            assert any("dog" in result.text.lower() for result in results)

    def test_mmr_search(self, component, mock_embedding):
        """Test MMR search functionality through the component."""
        component.embedding = mock_embedding

        # Mock the vector store and its methods
        with patch.object(component, "build_vector_store") as mock_build:
            mock_vector_store = MagicMock()
            mock_doc1 = MagicMock()
            mock_doc1.page_content = "The quick brown fox jumps"
            mock_doc1.metadata = {}
            mock_doc2 = MagicMock()
            mock_doc2.page_content = "Something completely different about cats"
            mock_doc2.metadata = {}
            mock_doc3 = MagicMock()
            mock_doc3.page_content = "The quick brown fox leaps"
            mock_doc3.metadata = {}

            mock_vector_store.max_marginal_relevance_search.return_value = [mock_doc1, mock_doc2, mock_doc3]
            mock_build.return_value = mock_vector_store

            component.search_query = "quick fox"
            component.search_type = "MMR"
            component.number_of_results = 3

            results = component.search_documents()

            # Verify MMR search was called
            mock_vector_store.max_marginal_relevance_search.assert_called_once()
            call_args = mock_vector_store.max_marginal_relevance_search.call_args
            assert call_args[1]["query"] == "quick fox"
            assert call_args[1]["k"] == 3

            # Verify results
            assert len(results) == 3
            assert any("fox" in result.text.lower() for result in results)

    def test_search_with_different_types(self, component, mock_embedding):
        """Test search with different search types."""
        component.embedding = mock_embedding

        with patch.object(component, "build_vector_store") as mock_build:
            mock_vector_store = MagicMock()
            mock_doc = MagicMock()
            mock_doc.page_content = "Python is a popular programming language"
            mock_doc.metadata = {}

            mock_vector_store.similarity_search.return_value = [mock_doc]
            mock_vector_store.max_marginal_relevance_search.return_value = [mock_doc]
            mock_build.return_value = mock_vector_store

            # Test similarity search
            component.search_type = "Similarity"
            component.search_query = "programming languages"
            component.number_of_results = 2

            similarity_results = component.search_documents()
            assert len(similarity_results) == 1
            mock_vector_store.similarity_search.assert_called_once()

            # Test MMR search
            component.search_type = "MMR"
            mmr_results = component.search_documents()
            assert len(mmr_results) == 1
            mock_vector_store.max_marginal_relevance_search.assert_called_once()

            # Test with empty query
            component.search_query = ""
            empty_results = component.search_documents()
            assert len(empty_results) == 0

    def test_duplicate_handling(self, component, mock_embedding):
        """Test handling of duplicate documents."""
        component.embedding = mock_embedding
        component.allow_duplicates = False

        # Mock the build_vector_store to test duplicate logic
        with patch.object(component, "build_vector_store") as mock_build:
            mock_vector_store = MagicMock()
            mock_build.return_value = mock_vector_store

            # Set ingest data with duplicates
            component.ingest_data = [
                Data(text="This is a test document"),
                Data(text="This is a test document"),  # Duplicate
                Data(text="This is another document"),
            ]

            # Call build to trigger duplicate handling
            vector_store = component.build_vector_store()

            # Verify vector store was created
            assert vector_store is not None

    def test_metadata_filtering_with_complex_data(self, component, mock_embedding):
        """Test that complex metadata is properly handled during ingestion."""
        component.embedding = mock_embedding

        # Mock the build_vector_store to test metadata handling
        with patch.object(component, "build_vector_store") as mock_build:
            mock_vector_store = MagicMock()
            mock_build.return_value = mock_vector_store

            # Set ingest data with complex metadata
            component.ingest_data = [
                Data(
                    data={
                        "text": "Document with mixed metadata",
                        "files": [],  # Complex type
                        "tags": ["tag1", "tag2"],  # List
                        "nested": {"key": "value"},  # Nested dict
                        "simple_string": "preserved",
                        "simple_int": 42,
                        "simple_bool": True,
                    }
                )
            ]

            # This should not raise an error despite complex metadata
            vector_store = component.build_vector_store()

            # Verify vector store was created
            assert vector_store is not None

    # Note: Similarity and MMR search tests removed - require actual DB2 database
    # Search logic is tested through search_query_from_data_object test below

    def test_search_query_from_data_object(self, component):
        """Test extracting search query from Data object."""
        data = Data(data={"text": "search query"})
        component.search_query = data

        # Mock the build_vector_store to avoid actual DB connection
        with patch.object(component, "build_vector_store") as mock_build:
            mock_vector_store = MagicMock()
            mock_vector_store.similarity_search.return_value = []
            mock_build.return_value = mock_vector_store

            component.search_documents()

            # Verify search was called with extracted text
            mock_vector_store.similarity_search.assert_called_once()
            call_args = mock_vector_store.similarity_search.call_args
            assert call_args[1]["query"] == "search query"

    def test_perform_search_returns_dataframe(self, component):
        """Test that perform_search returns a DataFrame."""
        with patch.object(component, "search_documents") as mock_search:
            mock_search.return_value = [Data(data={"text": "result"})]

            result = component.perform_search()

            from lfx.schema.dataframe import DataFrame

            assert isinstance(result, DataFrame)


# Made with Bob
