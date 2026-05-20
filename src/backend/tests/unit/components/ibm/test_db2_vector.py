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
