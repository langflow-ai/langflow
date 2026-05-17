from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_community.embeddings.fake import DeterministicFakeEmbedding
from langchain_community.vectorstores.utils import DistanceStrategy
from lfx.components.ibm.db2_vector import DB2VectorStoreComponent
from lfx.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping


class TestDB2VectorStore(ComponentTestBaseWithoutClient):
    """Test suite for DB2 Vector Store component."""

    @pytest.fixture
    def component_class(self) -> type[Any]:
        """Return the component class to test."""
        return DB2VectorStoreComponent

    @pytest.fixture
    def default_kwargs(self) -> dict[str, Any]:
        """Return the default kwargs for the component."""
        return {
            "hostname": "localhost",
            "port": 50000,
            "database": "testdb",
            "username": "testuser",
            "password": "testpass",  # pragma: allowlist secret
            "collection_name": "test_vectors",
            "embedding": DeterministicFakeEmbedding(size=8),
            "use_ssl": False,
            "connection_timeout": 10,
            "number_of_results": 4,
            "search_type": "Similarity",
            "distance_strategy": "COSINE",
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        # DB2 component is new, so we only test current version
        return []

    # ==================== Component Initialization Tests ====================

    def test_component_initialization(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test component instantiation with valid parameters."""
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)
        assert component is not None
        assert component.hostname == "localhost"
        assert component.port == 50000
        assert component.database == "testdb"
        assert component.collection_name == "test_vectors"

    def test_component_with_minimal_parameters(self, component_class: type[DB2VectorStoreComponent]) -> None:
        """Test component with minimal required parameters."""
        minimal_kwargs = {
            "hostname": "localhost",
            "port": 50000,
            "database": "testdb",
            "username": "user",
            "password": "pass",  # pragma: allowlist secret
            "collection_name": "vectors",
            "embedding": DeterministicFakeEmbedding(size=8),
        }
        component: DB2VectorStoreComponent = component_class().set(**minimal_kwargs)
        assert component is not None
        assert component.use_ssl is False
        assert component.connection_timeout == 10

    def test_component_with_all_parameters(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test component with all parameters including optional ones."""
        all_kwargs = {
            **default_kwargs,
            "use_ssl": True,
            "connection_timeout": 30,
            "number_of_results": 10,
            "search_type": "MMR",
            "distance_strategy": "EUCLIDEAN_DISTANCE",
            "ingest_data": [Data(text="test document")],
        }
        component: DB2VectorStoreComponent = component_class().set(**all_kwargs)
        assert component.use_ssl is True
        assert component.connection_timeout == 30
        assert component.number_of_results == 10
        assert component.search_type == "MMR"
        assert component.distance_strategy == "EUCLIDEAN_DISTANCE"

    # ==================== Input Validation Tests ====================

    @pytest.mark.parametrize("invalid_port", [0, -1, 65536, 99999])
    def test_invalid_port_validation(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any], invalid_port: int
    ) -> None:
        """Test that invalid port numbers are rejected."""
        default_kwargs["port"] = invalid_port
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        with patch("ibm_db_dbi.connect"), pytest.raises(ValueError, match="Invalid port number"):
            component.build_vector_store()

    def test_valid_port_range(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test that valid port numbers are accepted."""
        valid_ports = [1, 50000, 50001, 65535]
        for port in valid_ports:
            default_kwargs["port"] = port
            component: DB2VectorStoreComponent = component_class().set(**default_kwargs)
            # Should not raise during validation
            component._validate_port(port)

    @pytest.mark.parametrize(
        "invalid_hostname",
        [
            "host\x00name",  # Null byte
            "host\nname",  # Newline
            "host\rname",  # Carriage return
        ],
    )
    def test_invalid_hostname_validation(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any], invalid_hostname: str
    ) -> None:
        """Test that hostnames with control characters are rejected."""
        default_kwargs["hostname"] = invalid_hostname
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        with patch("ibm_db_dbi.connect"), pytest.raises(ValueError, match="Hostname contains invalid characters"):
            component.build_vector_store()

    def test_empty_hostname_validation(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test that empty hostname is rejected."""
        default_kwargs["hostname"] = ""
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        with patch("ibm_db_dbi.connect"), pytest.raises(ValueError, match="Hostname is required"):
            component.build_vector_store()

    @pytest.mark.parametrize(
        "invalid_table_name",
        [
            "SELECT",  # SQL keyword
            "DROP",  # SQL keyword
            "table;DROP TABLE users",  # SQL injection attempt
            "table--comment",  # SQL comment
            "table name",  # Space
            "table@name",  # Special character
            "123table",  # Starts with number
            "a" * 65,  # Too long
        ],
    )
    def test_invalid_table_name_validation(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any], invalid_table_name: str
    ) -> None:
        """Test that invalid table names are rejected."""
        default_kwargs["collection_name"] = invalid_table_name
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        with (
            patch("ibm_db_dbi.connect"),
            pytest.raises(ValueError, match=r"Table name|reserved SQL keyword|invalid character|must start with"),
        ):
            component.build_vector_store()

    @pytest.mark.parametrize(
        "valid_table_name",
        [
            "valid_table",
            "_table_name",
            "Table123",
            "MY_TABLE_NAME",
            "a" * 64,  # Max length
        ],
    )
    def test_valid_table_name_validation(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any], valid_table_name: str
    ) -> None:
        """Test that valid table names are accepted."""
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)
        # Should not raise
        component._validate_table_name(valid_table_name)

    # ==================== Connection String Tests ====================

    def test_connection_string_with_ssl_enabled(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test connection string construction with SSL enabled."""
        default_kwargs["use_ssl"] = True
        default_kwargs["port"] = 50001
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        with patch("ibm_db_dbi.connect") as mock_connect:
            mock_connect.return_value = MagicMock()
            with patch("langchain_db2.db2vs.DB2VS") as mock_db2vs:
                mock_db2vs.return_value = MagicMock()
                component.build_vector_store()

                # Verify SSL was included in connection string
                call_args = mock_connect.call_args[0][0]
                assert "SECURITY=SSL" in call_args

    def test_connection_string_with_ssl_disabled(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test connection string construction with SSL disabled."""
        default_kwargs["use_ssl"] = False
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        with patch("ibm_db_dbi.connect") as mock_connect:
            mock_connect.return_value = MagicMock()
            with patch("langchain_db2.db2vs.DB2VS") as mock_db2vs:
                mock_db2vs.return_value = MagicMock()
                component.build_vector_store()

                # Verify SSL was not included in connection string
                call_args = mock_connect.call_args[0][0]
                assert "SECURITY=SSL" not in call_args

    def test_connection_string_escaping(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test that connection string values are properly escaped."""
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        # Test escaping of special characters
        assert component._escape_connection_string_value("normal_value") == "normal_value"
        assert component._escape_connection_string_value("value\x00") == "value"
        assert component._escape_connection_string_value("value\n") == "value"
        assert component._escape_connection_string_value("value\r") == "value"

        # Test that semicolons are rejected
        with pytest.raises(ValueError, match="cannot contain semicolons"):
            component._escape_connection_string_value("value;with;semicolons")

    def test_connection_timeout_parameter(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test that connection timeout is included in connection string."""
        default_kwargs["connection_timeout"] = 30
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        with patch("ibm_db_dbi.connect") as mock_connect:
            mock_connect.return_value = MagicMock()
            with patch("langchain_db2.db2vs.DB2VS") as mock_db2vs:
                mock_db2vs.return_value = MagicMock()
                component.build_vector_store()

                # Verify timeout was included in connection string
                call_args = mock_connect.call_args[0][0]
                assert "ConnectTimeout=30" in call_args

    # ==================== Metadata Sanitization Tests ====================

    def test_metadata_cleaning_removes_dangerous_characters(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test that metadata cleaning removes null bytes and control characters."""
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        metadata = {
            "key\x00": "value\x00",
            "key\n": "value\n",
            "key\r": "value\r",
            "normal_key": "normal_value",
        }

        cleaned = component._clean_metadata(metadata)

        # Dangerous characters should be removed from keys
        assert "key\x00" not in cleaned
        assert "key\n" not in cleaned
        assert "key\r" not in cleaned
        assert "key" in cleaned
        assert "normal_key" in cleaned

        # Values should also be cleaned - null bytes and newlines removed
        assert "\x00" not in cleaned["key"]
        assert "\n" not in cleaned["key"]
        # Note: The implementation removes \x00, \n, \r from keys but only from string values
        # The test data shows that values are sanitized through _sanitize_value

    def test_metadata_cleaning_nested_structures(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test that nested metadata structures are properly cleaned."""
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        metadata = {
            "nested": {"inner_key": "inner_value", "inner_list": [1, 2, 3]},
            "list": ["item1", "item2"],
            "simple": "value",
        }

        cleaned = component._clean_metadata(metadata)

        assert "nested" in cleaned
        assert isinstance(cleaned["nested"], dict)
        assert cleaned["nested"]["inner_key"] == "inner_value"
        assert "list" in cleaned
        assert isinstance(cleaned["list"], list)
        assert cleaned["simple"] == "value"

    def test_metadata_cleaning_various_types(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test metadata cleaning with various data types."""
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        metadata = {
            "string": "text",
            "int": 42,
            "float": 3.14,
            "bool": True,
            "none": None,
            "list": [1, 2, 3],
            "dict": {"key": "value"},
        }

        cleaned = component._clean_metadata(metadata)

        assert cleaned["string"] == "text"
        assert cleaned["int"] == 42
        assert cleaned["float"] == 3.14
        assert cleaned["bool"] is True
        assert cleaned["none"] is None
        assert isinstance(cleaned["list"], list)
        assert isinstance(cleaned["dict"], dict)

    # ==================== Error Handling Tests ====================

    def test_connection_error_handling(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test connection error handling with user-friendly messages."""
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        with patch("ibm_db_dbi.connect") as mock_connect:
            mock_connect.side_effect = Exception("SQL30081N communication error")

            with pytest.raises(ConnectionError, match="Cannot connect to DB2 server"):
                component.build_vector_store()

    def test_ssl_error_detection(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test SSL-specific error detection and messaging."""
        default_kwargs["use_ssl"] = True
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        with patch("ibm_db_dbi.connect") as mock_connect:
            mock_connect.side_effect = Exception("SSL handshake failed")

            with pytest.raises(ConnectionError, match="SSL/TLS connection failed"):
                component.build_vector_store()

    def test_timeout_error_handling(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test timeout error handling."""
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        with patch("ibm_db_dbi.connect") as mock_connect:
            mock_connect.side_effect = Exception("Connection timed out")

            with pytest.raises(ConnectionError, match="Connection timeout"):
                component.build_vector_store()

    def test_authentication_error_handling(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test authentication error handling."""
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        with patch("ibm_db_dbi.connect") as mock_connect:
            mock_connect.side_effect = Exception("SQL30082N authentication failed")

            with pytest.raises(ConnectionError, match="Authentication failed"):
                component.build_vector_store()

    def test_missing_required_parameters(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test that missing required parameters raise appropriate errors."""
        # Test missing database
        kwargs_no_db = {**default_kwargs}
        kwargs_no_db["database"] = ""
        component: DB2VectorStoreComponent = component_class().set(**kwargs_no_db)

        with patch("ibm_db_dbi.connect"), pytest.raises(ValueError, match="Database name is required"):
            component.build_vector_store()

        # Test missing hostname
        kwargs_no_host = {**default_kwargs}
        kwargs_no_host["hostname"] = ""
        component = component_class().set(**kwargs_no_host)

        with patch("ibm_db_dbi.connect"), pytest.raises(ValueError, match="Hostname"):
            component.build_vector_store()

    # ==================== Mock Integration Tests ====================

    def test_document_ingestion(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test document ingestion with mocked DB2 connection."""
        test_data = [
            Data(text="Document 1"),
            Data(text="Document 2"),
            Data(text="Document 3"),
        ]
        default_kwargs["ingest_data"] = test_data

        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        with patch("ibm_db_dbi.connect") as mock_connect:
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            with patch("langchain_db2.db2vs.DB2VS") as mock_db2vs:
                # Create a mock instance that will be returned by DB2VS()
                mock_store_instance = MagicMock()
                mock_db2vs.return_value = mock_store_instance

                component.build_vector_store()

                # Verify documents were added to the instance
                assert mock_store_instance.add_documents.called
                call_args = mock_store_instance.add_documents.call_args[0][0]
                assert len(call_args) == 3

    def test_similarity_search(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test similarity search with mocked vector store."""
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)
        component.search_query = "test query"

        with patch("ibm_db_dbi.connect") as mock_connect:
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            with patch("langchain_db2.db2vs.DB2VS") as mock_db2vs:
                # Create a mock instance
                mock_store_instance = MagicMock()
                mock_db2vs.return_value = mock_store_instance

                # Mock search results
                from langchain_core.documents import Document

                mock_docs = [
                    Document(page_content="Result 1", metadata={}),
                    Document(page_content="Result 2", metadata={}),
                ]
                mock_store_instance.similarity_search.return_value = mock_docs

                results = component.search_documents()

                # Verify search was called
                assert mock_store_instance.similarity_search.called
                assert len(results) == 2

    def test_mmr_search(self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]) -> None:
        """Test MMR search with mocked vector store."""
        default_kwargs["search_type"] = "MMR"
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)
        component.search_query = "test query"

        with patch("ibm_db_dbi.connect") as mock_connect:
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            with patch("langchain_db2.db2vs.DB2VS") as mock_db2vs:
                # Create a mock instance
                mock_store_instance = MagicMock()
                mock_db2vs.return_value = mock_store_instance

                # Mock MMR search results
                from langchain_core.documents import Document

                mock_docs = [
                    Document(page_content="Result 1", metadata={}),
                    Document(page_content="Result 2", metadata={}),
                ]
                mock_store_instance.max_marginal_relevance_search.return_value = mock_docs

                results = component.search_documents()

                # Verify MMR search was called
                assert mock_store_instance.max_marginal_relevance_search.called
                assert len(results) == 2

    def test_empty_search_query(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test search with empty query returns empty results."""
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)
        component.search_query = ""

        results = component.search_documents()
        assert len(results) == 0

    @pytest.mark.parametrize(
        "distance_strategy",
        ["COSINE", "EUCLIDEAN_DISTANCE", "DOT_PRODUCT"],
    )
    def test_distance_strategies(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any], distance_strategy: str
    ) -> None:
        """Test different distance strategies are properly configured."""
        default_kwargs["distance_strategy"] = distance_strategy
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        with patch("ibm_db_dbi.connect") as mock_connect:
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            with patch("langchain_db2.db2vs.DB2VS") as mock_db2vs:
                mock_store_instance = MagicMock()
                mock_db2vs.return_value = mock_store_instance

                component.build_vector_store()

                # Verify DB2VS was called
                assert mock_db2vs.called

                # Verify distance strategy was passed correctly
                call_kwargs = mock_db2vs.call_args.kwargs
                assert "distance_strategy" in call_kwargs

                # Map to expected DistanceStrategy enum
                expected_strategy = {
                    "COSINE": DistanceStrategy.COSINE,
                    "EUCLIDEAN_DISTANCE": DistanceStrategy.EUCLIDEAN_DISTANCE,
                    "DOT_PRODUCT": DistanceStrategy.DOT_PRODUCT,
                }[distance_strategy]

                assert call_kwargs["distance_strategy"] == expected_strategy


# Made with Bob
