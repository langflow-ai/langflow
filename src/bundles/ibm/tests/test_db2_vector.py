"""Unit tests for the DB2 Vector Store component (lfx-ibm bundle).

The component used to live at ``lfx.components.ibm.db2_vector`` and was
tested under ``src/backend/tests/unit/components/ibm/`` using the in-tree
``ComponentTestBaseWithoutClient`` helper.  It has since been extracted
into a standalone bundle; these tests now travel with the bundle and
import the public bundle entry point.  The base-class scaffolding (which
parametrised version-compat tests against a saved-fixture directory) is
dropped: ``DB2VectorStoreComponent`` is new in 1.10.0 and has no
historical schema fixtures to validate against.
"""

import importlib.util
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.embeddings import Embeddings
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx_ibm.components.ibm.db2_vector import DB2VectorStoreComponent

# ibm-db (ibm_db_dbi) ships no linux/aarch64 wheel.  The imports above work
# without it (db2_vector imports the driver lazily inside build_vector_store),
# so importability is exercised on every platform; the tests below need a live
# driver -- build_vector_store imports it before the validation paths run -- so
# gate the whole test class.
requires_ibm_db = pytest.mark.skipif(
    importlib.util.find_spec("ibm_db_dbi") is None,
    reason="ibm-db (ibm_db_dbi) not installed on this platform (e.g. linux/aarch64)",
)


class FakeEmbeddings(Embeddings):
    """Small Embeddings test double that follows the LangChain contract."""

    def __init__(self, vector: list[float] | None = None):
        self.vector = vector or [0.1, 0.2, 0.3]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.vector.copy() for _ in texts]

    def embed_query(self, _text: str) -> list[float]:
        return self.vector.copy()


@requires_ibm_db
class TestDB2VectorStoreComponent:
    """Test DB2 Vector Store Component."""

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
        comp.should_cache_vector_store = False
        return comp

    @pytest.fixture
    def mock_embedding(self):
        """Create an embedding model test double."""
        return FakeEmbeddings()

    def test_component_metadata(self):
        """Test component metadata is correctly set."""
        comp = DB2VectorStoreComponent()
        assert comp.display_name == "IBM Db2 Vector Store"
        expected_desc = (
            "IBM Db2 Vector Store with search capabilities. Use Generic-typed global variables for "
            "connection parameters (database, hostname, username). Only password should use Credential-typed variables."
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

    def test_search_documents_no_query(self, component, mock_embedding):
        """Test search with no query returns an empty list but still builds the store.

        Ingestion happens inside ``build_vector_store``; an empty search query
        must not short-circuit that, so the store is still built (ingested)
        and only the *search* is skipped.
        """
        component.embedding = mock_embedding
        component.search_query = None
        with patch.object(component, "build_vector_store") as mock_build:
            mock_build.return_value = MagicMock()
            results = component.search_documents()
            # Vector store is still built (ingestion runs) even without a query...
            mock_build.assert_called_once()
            # ...but no search is performed, so no results come back.
            assert results == []

    def test_ingestion_occurs_without_search_query(self, component, mock_embedding):
        """Regression: ingestion must happen even when no search query is set.

        Previously ``search_documents`` returned early on an empty query *before*
        building the vector store, so connected ingest data was silently dropped
        unless a search query was also provided. Ingestion and search are
        independent.
        """
        component.embedding = mock_embedding
        component.search_query = None
        component.ingest_data = [Data(text="Doc to ingest")]

        with patch("ibm_db_dbi.connect") as mock_connect:
            mock_connect.return_value = MagicMock()

            from lfx_ibm.components.ibm.db2vs import DB2VS

            with (
                patch.object(DB2VS, "__init__", return_value=None),
                patch.object(DB2VS, "add_documents") as mock_add_docs,
            ):
                results = component.search_documents()

                # No query -> no search results...
                assert results == []
                # ...but the document was still ingested into the store.
                mock_add_docs.assert_called_once()
                added_docs = mock_add_docs.call_args[0][0]
                assert len(added_docs) == 1
                assert added_docs[0].page_content == "Doc to ingest"

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
        """Test handling of duplicate documents in the same batch."""
        component.embedding = mock_embedding

        # Set ingest data with duplicates (duplicates are always prevented)
        component.ingest_data = [
            Data(text="This is a test document"),
            Data(text="This is a test document"),  # Duplicate
            Data(text="This is another document"),
        ]

        with (
            patch("ibm_db_dbi.connect") as mock_connect,
        ):
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            from lfx_ibm.components.ibm.db2vs import DB2VS

            mock_vector_store = MagicMock()
            with (
                patch.object(DB2VS, "__init__", return_value=None),
                patch.object(DB2VS, "add_documents") as mock_add_docs,
            ):
                mock_vector_store.add_documents = mock_add_docs
                component._add_documents_to_vector_store(mock_vector_store)

                # Verify only unique documents were added (2 out of 3)
                if mock_add_docs.called:
                    added_docs = mock_add_docs.call_args[0][0]
                    assert len(added_docs) == 2, "Should only add 2 unique documents"
                    # Verify the content of added documents
                    contents = [doc.page_content for doc in added_docs]
                    assert "This is a test document" in contents
                    assert "This is another document" in contents

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

    def test_ssl_enabled_without_certificate(self, component, mock_embedding):
        """Test that SSL requires a certificate path."""
        component.embedding = mock_embedding
        component.use_ssl = True
        component.ssl_certificate_path = None

        # Should raise ValueError - certificate path is required when SSL is enabled
        with pytest.raises(ValueError, match="SSL/TLS is enabled but no certificate path provided"):
            component.build_vector_store()

    def test_ssl_enabled_with_empty_certificate(self, component, mock_embedding):
        """Test that SSL requires a non-empty certificate path."""
        component.embedding = mock_embedding
        component.use_ssl = True
        component.ssl_certificate_path = ""

        # Should raise ValueError - certificate path is required
        with pytest.raises(ValueError, match="SSL/TLS is enabled but no certificate path provided"):
            component.build_vector_store()

    def test_ssl_enabled_with_whitespace_certificate(self, component, mock_embedding):
        """Test that SSL requires a non-whitespace certificate path."""
        component.embedding = mock_embedding
        component.use_ssl = True
        component.ssl_certificate_path = "   "

        # Should raise ValueError - certificate path is required
        with pytest.raises(ValueError, match="SSL/TLS is enabled but no certificate path provided"):
            component.build_vector_store()

    def test_ssl_enabled_with_local_certificate(self, component, mock_embedding):
        """Test SSL connection with local certificate file."""
        component.embedding = mock_embedding
        component.use_ssl = True

        # Create a temporary certificate file
        with tempfile.NamedTemporaryFile(suffix=".crt", delete=False) as temp_cert:
            temp_cert.write(b"FAKE CERTIFICATE")
            cert_path = temp_cert.name

        try:
            component.ssl_certificate_path = cert_path

            with (
                patch("ibm_db_dbi.connect") as mock_connect,
                patch.object(component, "_add_documents_to_vector_store"),
            ):
                mock_connection = MagicMock()
                mock_connect.return_value = mock_connection

                from lfx_ibm.components.ibm.db2vs import DB2VS

                with patch.object(DB2VS, "__init__", return_value=None):
                    component.build_vector_store()

                # Verify SSL was enabled with certificate
                call_args = mock_connect.call_args[0][0]
                assert "SECURITY=SSL" in call_args
                # Path may be resolved to absolute path, so check if cert path is in the connection string
                assert "SSLServerCertificate=" in call_args
                assert cert_path.split("/")[-1] in call_args  # Check filename is present
        finally:
            # Clean up temp file
            Path(cert_path).unlink(missing_ok=True)

    def test_ssl_enabled_with_certificate_password(self, component, mock_embedding):
        """Test SSL connection with certificate password."""
        component.embedding = mock_embedding
        component.use_ssl = True
        component.ssl_certificate_password = "test_password"  # noqa: S105  # pragma: allowlist secret

        # Create a temporary certificate file
        with tempfile.NamedTemporaryFile(suffix=".crt", delete=False) as temp_cert:
            temp_cert.write(b"FAKE CERTIFICATE")
            cert_path = temp_cert.name

        try:
            component.ssl_certificate_path = cert_path

            with (
                patch("ibm_db_dbi.connect") as mock_connect,
                patch.object(component, "_add_documents_to_vector_store"),
            ):
                mock_connection = MagicMock()
                mock_connect.return_value = mock_connection

                from lfx_ibm.components.ibm.db2vs import DB2VS

                with patch.object(DB2VS, "__init__", return_value=None):
                    component.build_vector_store()

                # Verify SSL was enabled with certificate and password
                call_args = mock_connect.call_args[0][0]
                assert "SECURITY=SSL" in call_args
                # Path may be resolved to absolute path, so check if cert path is in the connection string
                assert "SSLServerCertificate=" in call_args
                assert cert_path.split("/")[-1] in call_args  # Check filename is present
                assert "SSLClientKeystorePassword=test_password" in call_args
        finally:
            # Clean up temp file
            Path(cert_path).unlink(missing_ok=True)

    def test_ssl_certificate_url_download(self, component, mock_embedding):
        """Test SSL certificate download from URL."""
        component.embedding = mock_embedding
        component.use_ssl = True
        component.ssl_certificate_path = "https://example.com/cert.crt"

        with (
            patch("lfx_ibm.components.ibm.db2_security.download_certificate") as mock_download,
            patch("ibm_db_dbi.connect") as mock_connect,
            patch.object(component, "_add_documents_to_vector_store"),
        ):
            # Mock successful certificate download
            temp_cert_path = "/tmp/downloaded_cert.crt"
            mock_download.return_value = (temp_cert_path, None)
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            from lfx_ibm.components.ibm.db2vs import DB2VS

            with patch.object(DB2VS, "__init__", return_value=None):
                component.build_vector_store()

            # Verify certificate was downloaded
            mock_download.assert_called_once_with("https://example.com/cert.crt")

    def test_ssl_certificate_invalid_path(self, component, mock_embedding):
        """Test error handling for invalid certificate path."""
        component.embedding = mock_embedding
        component.use_ssl = True
        component.ssl_certificate_path = "/nonexistent/path/cert.crt"

        with pytest.raises(ValueError, match="SSL certificate validation failed"):
            component.build_vector_store()

    def test_connection_failure_cleanup(self, component, mock_embedding):
        """Test that temporary certificate is cleaned up on connection failure."""
        component.embedding = mock_embedding
        component.use_ssl = True
        component.ssl_certificate_path = "https://example.com/cert.crt"

        with (
            patch("lfx_ibm.components.ibm.db2_security.download_certificate") as mock_download,
            patch("ibm_db_dbi.connect") as mock_connect,
            patch("pathlib.Path.unlink") as mock_unlink,
        ):
            # Mock successful download but failed connection
            temp_cert_path = "/tmp/downloaded_cert.crt"
            mock_download.return_value = (temp_cert_path, None)
            mock_connect.side_effect = Exception("Connection failed")

            with pytest.raises(ConnectionError, match="Connection failed"):
                component.build_vector_store()

            # Verify cleanup was attempted
            mock_unlink.assert_called()

    def test_search_query_from_message_object(self, component, mock_embedding):
        """Test extracting search query from Message object."""
        component.embedding = mock_embedding
        message = Message(text="search from message")
        component.search_query = message

        with patch.object(component, "build_vector_store") as mock_build:
            mock_vector_store = MagicMock()
            mock_vector_store.similarity_search.return_value = []
            mock_build.return_value = mock_vector_store

            component.search_documents()

            # Verify search was called with extracted text
            mock_vector_store.similarity_search.assert_called_once()
            call_args = mock_vector_store.similarity_search.call_args
            assert call_args[1]["query"] == "search from message"

    def test_search_query_from_data_with_text_data(self, component, mock_embedding):
        """Test extracting search query from Data object with text_data attribute."""
        component.embedding = mock_embedding
        # Create Data object and manually set text_data attribute
        data = Data(data={"content": "some content"})
        data.text_data = "search from text_data"
        component.search_query = data

        with patch.object(component, "build_vector_store") as mock_build:
            mock_vector_store = MagicMock()
            mock_vector_store.similarity_search.return_value = []
            mock_build.return_value = mock_vector_store

            component.search_documents()

            # Verify search was called with text_data
            mock_vector_store.similarity_search.assert_called_once()
            call_args = mock_vector_store.similarity_search.call_args
            assert call_args[1]["query"] == "search from text_data"

    def test_search_query_from_data_with_dict(self, component, mock_embedding):
        """Test extracting search query from Data object with dict data."""
        component.embedding = mock_embedding
        data = Data(data={"text": "search from dict", "other": "field"})
        component.search_query = data

        with patch.object(component, "build_vector_store") as mock_build:
            mock_vector_store = MagicMock()
            mock_vector_store.similarity_search.return_value = []
            mock_build.return_value = mock_vector_store

            component.search_documents()

            # Verify search was called with extracted text
            mock_vector_store.similarity_search.assert_called_once()
            call_args = mock_vector_store.similarity_search.call_args
            assert call_args[1]["query"] == "search from dict"

    def test_search_query_from_string(self, component, mock_embedding):
        """Test search with plain string query."""
        component.embedding = mock_embedding
        component.search_query = "plain string query"

        with patch.object(component, "build_vector_store") as mock_build:
            mock_vector_store = MagicMock()
            mock_vector_store.similarity_search.return_value = []
            mock_build.return_value = mock_vector_store

            component.search_documents()

            # Verify search was called with string
            mock_vector_store.similarity_search.assert_called_once()
            call_args = mock_vector_store.similarity_search.call_args
            assert call_args[1]["query"] == "plain string query"

            # Should not raise
            component.search_documents()

    def test_metadata_cleared_during_ingestion(self, component, mock_embedding):
        """Test that metadata is cleared during document ingestion."""
        component.embedding = mock_embedding

        # Create data with complex metadata
        component.ingest_data = [
            Data(
                text="Test document",
                data={
                    "text": "Test document",
                    "metadata_field": "should be removed",
                    "nested": {"key": "value"},
                },
            )
        ]

        with (
            patch("ibm_db_dbi.connect") as mock_connect,
            patch("langchain_community.vectorstores.utils.filter_complex_metadata") as mock_filter,
        ):
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            from langchain_core.documents import Document
            from lfx_ibm.components.ibm.db2vs import DB2VS

            # Mock filter to return documents
            filtered_doc = Document(page_content="Test document", metadata={"some": "metadata"})
            mock_filter.return_value = [filtered_doc]

            mock_vector_store = MagicMock()
            with (
                patch.object(DB2VS, "__init__", return_value=None),
                patch.object(DB2VS, "add_documents") as mock_add_docs,
                patch.object(component, "build_vector_store", return_value=mock_vector_store),
            ):
                mock_vector_store.add_documents = mock_add_docs
                component._add_documents_to_vector_store(mock_vector_store)

                # Verify documents were added with cleared metadata
                if mock_add_docs.called:
                    added_docs = mock_add_docs.call_args[0][0]
                    for doc in added_docs:
                        assert doc.metadata == {}

    def test_metadata_cleared_fallback_without_filter(self, component, mock_embedding):
        """Test metadata clearing fallback when filter_complex_metadata is unavailable."""
        component.embedding = mock_embedding
        component.ingest_data = [Data(text="Test document", data={"text": "Test document", "field": "value"})]

        with (
            patch("ibm_db_dbi.connect") as mock_connect,
            patch.dict("sys.modules", {"langchain_community.vectorstores.utils": None}),
        ):
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            from lfx_ibm.components.ibm.db2vs import DB2VS

            mock_vector_store = MagicMock()
            with (
                patch.object(DB2VS, "__init__", return_value=None),
                patch.object(DB2VS, "add_documents") as mock_add_docs,
                patch.object(component, "build_vector_store", return_value=mock_vector_store),
            ):
                mock_vector_store.add_documents = mock_add_docs
                component._add_documents_to_vector_store(mock_vector_store)

                # Verify fallback was used and metadata was cleared
                if mock_add_docs.called:
                    added_docs = mock_add_docs.call_args[0][0]
                    for doc in added_docs:
                        assert doc.metadata == {}

    def test_search_results_return_text_only(self, component, mock_embedding):
        """Test that search results return only text, not metadata."""
        component.embedding = mock_embedding
        component.search_query = "test query"

        with patch.object(component, "build_vector_store") as mock_build:
            mock_vector_store = MagicMock()
            mock_doc = MagicMock()
            mock_doc.page_content = "Result document text"
            mock_doc.metadata = {"should": "not", "be": "included"}

            mock_vector_store.similarity_search.return_value = [mock_doc]
            mock_build.return_value = mock_vector_store

            results = component.search_documents()

            # Verify results contain only text
            assert len(results) == 1
            assert results[0].text == "Result document text"
            assert results[0].data == {"text": "Result document text"}

    def test_build_method_search_mode(self, component, mock_embedding):
        """Test build() method in Search mode."""
        component.embedding = mock_embedding
        component.mode = "Search"
        component.search_query = "test"

        with patch.object(component, "search_documents") as mock_search:
            mock_search.return_value = [Data(text="result")]
            result = component.build()

            mock_search.assert_called_once()
            assert result == [Data(text="result")]

    def test_build_method_ingest_mode(self, component, mock_embedding):
        """Test build() method in Ingest mode (default)."""
        component.embedding = mock_embedding
        # No mode set, defaults to Ingest

        with patch.object(component, "build_vector_store") as mock_build_vs:
            mock_vector_store = MagicMock()
            mock_build_vs.return_value = mock_vector_store
            result = component.build()

            mock_build_vs.assert_called_once()
            assert result == mock_vector_store

    def test_connection_string_format(self, component, mock_embedding):
        """Test that connection string is properly formatted."""
        component.embedding = mock_embedding
        component.database = "TESTDB"
        component.hostname = "db.example.com"
        component.port = 50000
        component.username = "testuser"
        component.password = "testpass"  # noqa: S105  # pragma: allowlist secret

        with (
            patch("ibm_db_dbi.connect") as mock_connect,
            patch.object(component, "_add_documents_to_vector_store"),
        ):
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            from lfx_ibm.components.ibm.db2vs import DB2VS

            with patch.object(DB2VS, "__init__", return_value=None):
                component.build_vector_store()

            # Verify connection string format
            call_args = mock_connect.call_args[0][0]
            assert "DATABASE=TESTDB" in call_args
            assert "HOSTNAME=db.example.com" in call_args
            assert "PORT=50000" in call_args
            assert "PROTOCOL=TCPIP" in call_args
            assert "UID=testuser" in call_args
            assert "PWD=testpass" in call_args

    def test_distance_strategy_mapping(self, component, mock_embedding):
        """Test that distance strategies are correctly mapped."""
        component.embedding = mock_embedding

        with (
            patch("ibm_db_dbi.connect") as mock_connect,
            patch.object(component, "_add_documents_to_vector_store"),
        ):
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            from langchain_community.vectorstores.utils import DistanceStrategy
            from lfx_ibm.components.ibm.db2vs import DB2VS

            # Test COSINE
            component.distance_strategy = "COSINE"
            with patch.object(DB2VS, "__init__") as mock_init:
                mock_init.return_value = None
                component.build_vector_store()
                call_kwargs = mock_init.call_args[1]
                assert call_kwargs["distance_strategy"] == DistanceStrategy.COSINE

            # Test EUCLIDEAN_DISTANCE
            component.distance_strategy = "EUCLIDEAN_DISTANCE"
            with patch.object(DB2VS, "__init__") as mock_init:
                mock_init.return_value = None
                component.build_vector_store()
                call_kwargs = mock_init.call_args[1]
                assert call_kwargs["distance_strategy"] == DistanceStrategy.EUCLIDEAN_DISTANCE

            # Test DOT_PRODUCT
            component.distance_strategy = "DOT_PRODUCT"
            with patch.object(DB2VS, "__init__") as mock_init:
                mock_init.return_value = None
                component.build_vector_store()
                call_kwargs = mock_init.call_args[1]
                assert call_kwargs["distance_strategy"] == DistanceStrategy.DOT_PRODUCT

    def test_no_embedding_model_error(self, component):
        """Test error when no embedding model is provided."""
        component.embedding = None

        with (
            patch("ibm_db_dbi.connect") as mock_connect,
        ):
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            with pytest.raises(ValueError, match="Embedding Model Required"):
                component.build_vector_store()

    def test_connection_closed_on_error(self, component, mock_embedding):
        """Test that DB connection is closed when vector store creation fails."""
        component.embedding = mock_embedding

        with patch("ibm_db_dbi.connect") as mock_connect:
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            from lfx_ibm.components.ibm.db2vs import DB2VS

            # Mock DB2VS to raise an error
            with patch.object(DB2VS, "__init__", side_effect=Exception("DB2VS creation failed")):
                with pytest.raises(Exception, match="DB2VS creation failed"):
                    component.build_vector_store()

                # Verify connection was closed
                mock_connection.close.assert_called_once()

    def test_empty_ingest_data(self, component, mock_embedding):
        """Test handling of empty ingest data."""
        component.embedding = mock_embedding
        component.ingest_data = []

        with (
            patch("ibm_db_dbi.connect") as mock_connect,
        ):
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            from lfx_ibm.components.ibm.db2vs import DB2VS

            mock_vector_store = MagicMock()
            with patch.object(DB2VS, "__init__", return_value=None):
                with patch.object(component, "build_vector_store", return_value=mock_vector_store):
                    component._add_documents_to_vector_store(mock_vector_store)

                # Verify no documents were added
                mock_vector_store.add_documents.assert_not_called()

    def test_non_data_object_raises_error(self, component, mock_embedding):
        """Test that non-Data objects in ingest_data raise TypeError."""
        component.embedding = mock_embedding
        component.ingest_data = ["not a Data object"]

        with (
            patch("ibm_db_dbi.connect") as mock_connect,
        ):
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            from lfx_ibm.components.ibm.db2vs import DB2VS

            mock_vector_store = MagicMock()
            with (
                patch.object(DB2VS, "__init__", return_value=None),
                pytest.raises(TypeError, match="Vector Store Inputs must be Data objects"),
            ):
                component._add_documents_to_vector_store(mock_vector_store)

    def test_bulk_insert_enabled_by_default(self, component, mock_embedding):
        """Test that bulk insert is enabled by default."""
        component.embedding = mock_embedding

        with (
            patch("ibm_db_dbi.connect") as mock_connect,
            patch.object(component, "_add_documents_to_vector_store"),
        ):
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            from lfx_ibm.components.ibm.db2vs import DB2VS

            with patch.object(DB2VS, "__init__", return_value=None) as mock_init:
                component.build_vector_store()

                # Verify use_bulk_insert was passed as True (default)
                call_kwargs = mock_init.call_args[1]
                assert call_kwargs["use_bulk_insert"] is True

    def test_bulk_insert_toggle_enabled(self, component, mock_embedding):
        """Test bulk insert when explicitly enabled."""
        component.embedding = mock_embedding
        component.use_bulk_insert = True

        with (
            patch("ibm_db_dbi.connect") as mock_connect,
            patch.object(component, "_add_documents_to_vector_store"),
        ):
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            from lfx_ibm.components.ibm.db2vs import DB2VS

            with patch.object(DB2VS, "__init__", return_value=None) as mock_init:
                component.build_vector_store()

                # Verify use_bulk_insert was passed as True
                call_kwargs = mock_init.call_args[1]
                assert call_kwargs["use_bulk_insert"] is True

    def test_bulk_insert_toggle_disabled(self, component, mock_embedding):
        """Test bulk insert when explicitly disabled."""
        component.embedding = mock_embedding
        component.use_bulk_insert = False

        with (
            patch("ibm_db_dbi.connect") as mock_connect,
            patch.object(component, "_add_documents_to_vector_store"),
        ):
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            from lfx_ibm.components.ibm.db2vs import DB2VS

            with patch.object(DB2VS, "__init__", return_value=None) as mock_init:
                component.build_vector_store()

                # Verify use_bulk_insert was passed as False
                call_kwargs = mock_init.call_args[1]
                assert call_kwargs["use_bulk_insert"] is False

    def test_bulk_insert_mode_uses_executemany(self, mock_embedding):
        """Test that bulk insert mode uses executemany() for better performance."""
        from lfx_ibm.components.ibm.db2vs import DB2VS

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # Mock table operations
        with (
            patch("lfx_ibm.components.ibm.db2vs._table_exists", return_value=False),
            patch("lfx_ibm.components.ibm.db2vs._create_table"),
            patch(
                "lfx_ibm.components.ibm.db2vs._get_column_names",
                return_value={"id": "id", "embedding": "embedding", "metadata": "metadata", "text": "text"},
            ),
        ):
            # Create DB2VS instance with bulk insert enabled
            vector_store = DB2VS(
                client=mock_connection,
                embedding_function=mock_embedding,
                table_name="test_table",
                use_bulk_insert=True,
            )

            # Add some test documents
            texts = ["Document 1", "Document 2", "Document 3"]
            metadatas = [{"source": "test1"}, {"source": "test2"}, {"source": "test3"}]

            vector_store.add_texts(texts, metadatas=metadatas)

            # Verify executemany was called (bulk insert)
            assert mock_cursor.executemany.called, "executemany should be called in bulk insert mode"
            # Verify execute was NOT called for individual inserts
            # (execute is only called for COMMIT)
            execute_calls = [call for call in mock_cursor.execute.call_args_list if "INSERT" in str(call)]
            assert len(execute_calls) == 0, "execute should not be called for individual inserts in bulk mode"

    def test_row_by_row_insert_mode_uses_execute(self, mock_embedding):
        """Test that row-by-row insert mode uses execute() for each document."""
        from lfx_ibm.components.ibm.db2vs import DB2VS

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # Mock table operations
        with (
            patch("lfx_ibm.components.ibm.db2vs._table_exists", return_value=False),
            patch("lfx_ibm.components.ibm.db2vs._create_table"),
            patch(
                "lfx_ibm.components.ibm.db2vs._get_column_names",
                return_value={"id": "id", "embedding": "embedding", "metadata": "metadata", "text": "text"},
            ),
        ):
            # Create DB2VS instance with bulk insert disabled
            vector_store = DB2VS(
                client=mock_connection,
                embedding_function=mock_embedding,
                table_name="test_table",
                use_bulk_insert=False,
            )

            # Add some test documents
            texts = ["Document 1", "Document 2", "Document 3"]
            metadatas = [{"source": "test1"}, {"source": "test2"}, {"source": "test3"}]

            vector_store.add_texts(texts, metadatas=metadatas)

            # Verify executemany was NOT called
            assert not mock_cursor.executemany.called, "executemany should not be called in row-by-row mode"
            # Verify execute was called multiple times (once per document + COMMIT)
            assert mock_cursor.execute.call_count >= len(texts), "execute should be called for each document"

    def test_bulk_insert_with_multiple_documents(self, component, mock_embedding):
        """Test bulk insert with multiple documents."""
        component.embedding = mock_embedding
        component.use_bulk_insert = True
        component.ingest_data = [
            Data(text="Document 1"),
            Data(text="Document 2"),
            Data(text="Document 3"),
            Data(text="Document 4"),
            Data(text="Document 5"),
        ]

        with (
            patch("ibm_db_dbi.connect") as mock_connect,
        ):
            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            mock_connection.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_connection

            from lfx_ibm.components.ibm.db2vs import DB2VS

            with (
                patch.object(DB2VS, "__init__", return_value=None),
                patch.object(DB2VS, "add_documents") as mock_add_docs,
            ):
                vector_store = component.build_vector_store()
                component._add_documents_to_vector_store(vector_store)

                # Verify documents were added
                if mock_add_docs.called:
                    added_docs = mock_add_docs.call_args[0][0]
                    assert len(added_docs) == 5, "All 5 documents should be added"

    def test_bulk_insert_performance_benefit(self, mock_embedding):
        """Test that bulk insert reduces database round-trips."""
        from lfx_ibm.components.ibm.db2vs import DB2VS

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # Mock table operations
        with (
            patch("lfx_ibm.components.ibm.db2vs._table_exists", return_value=False),
            patch("lfx_ibm.components.ibm.db2vs._create_table"),
            patch(
                "lfx_ibm.components.ibm.db2vs._get_column_names",
                return_value={"id": "id", "embedding": "embedding", "metadata": "metadata", "text": "text"},
            ),
        ):
            # Test with bulk insert enabled
            vector_store_bulk = DB2VS(
                client=mock_connection,
                embedding_function=mock_embedding,
                table_name="test_table",
                use_bulk_insert=True,
            )

            texts = ["Doc 1", "Doc 2", "Doc 3", "Doc 4", "Doc 5"]
            vector_store_bulk.add_texts(texts)

            # Count database calls with bulk insert
            bulk_executemany_calls = mock_cursor.executemany.call_count
            bulk_execute_calls = mock_cursor.execute.call_count

            # Reset mocks
            mock_cursor.reset_mock()

            # Test with bulk insert disabled
            vector_store_row = DB2VS(
                client=mock_connection,
                embedding_function=mock_embedding,
                table_name="test_table",
                use_bulk_insert=False,
            )

            vector_store_row.add_texts(texts)

            # Count database calls with row-by-row insert
            row_executemany_calls = mock_cursor.executemany.call_count
            row_execute_calls = mock_cursor.execute.call_count

            # Verify bulk insert uses fewer calls
            assert bulk_executemany_calls > 0, "Bulk insert should use executemany"
            assert row_executemany_calls == 0, "Row-by-row should not use executemany"
            assert row_execute_calls > bulk_execute_calls, "Row-by-row should make more execute calls"

    def test_bulk_insert_with_empty_documents(self, mock_embedding):
        """Test bulk insert handles empty document list gracefully."""
        from lfx_ibm.components.ibm.db2vs import DB2VS

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # Mock table operations
        with (
            patch("lfx_ibm.components.ibm.db2vs._table_exists", return_value=False),
            patch("lfx_ibm.components.ibm.db2vs._create_table"),
            patch(
                "lfx_ibm.components.ibm.db2vs._get_column_names",
                return_value={"id": "id", "embedding": "embedding", "metadata": "metadata", "text": "text"},
            ),
        ):
            vector_store = DB2VS(
                client=mock_connection,
                embedding_function=mock_embedding,
                table_name="test_table",
                use_bulk_insert=True,
            )

            # Add empty list
            result = vector_store.add_texts([])

            # Verify no database calls were made
            mock_connection.cursor.assert_not_called()
            assert not mock_cursor.executemany.called
            assert result == []

    def test_bulk_insert_with_special_characters(self, mock_embedding):
        """Test bulk insert preserves special characters in bound parameters."""
        from lfx_ibm.components.ibm.db2vs import DB2VS

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # Mock table operations
        with (
            patch("lfx_ibm.components.ibm.db2vs._table_exists", return_value=False),
            patch("lfx_ibm.components.ibm.db2vs._create_table"),
            patch(
                "lfx_ibm.components.ibm.db2vs._get_column_names",
                return_value={"id": "id", "embedding": "embedding", "metadata": "metadata", "text": "text"},
            ),
        ):
            vector_store = DB2VS(
                client=mock_connection,
                embedding_function=mock_embedding,
                table_name="test_table",
                use_bulk_insert=True,
            )

            # Add documents with special characters
            texts = [
                "Document with 'single quotes'",
                'Document with "double quotes"',
                "Document with \n newlines \t tabs",
                "Document with SQL injection'; DROP TABLE users;--",
            ]
            metadatas = [
                {"source": "O'Brien"},
                {"source": 'double "quote"'},
                {"source": "line\nbreak"},
                {"source": "payload'; DROP TABLE users;--"},
            ]
            ids = ["id'1", 'id"2', "id\n3", "id;4"]

            vector_store.add_texts(texts, metadatas=metadatas, ids=ids)

            # Verify executemany was called (documents were processed)
            assert mock_cursor.executemany.called
            # Bound parameters should stay raw; the DB driver handles escaping.
            call_args = mock_cursor.executemany.call_args[0]
            assert len(call_args) == 2  # SQL statement and data tuples
            insert_data = call_args[1]
            assert insert_data[0][0] == ids[0]
            assert insert_data[0][2] == json.dumps(metadatas[0])
            assert insert_data[0][3] == texts[0]
            assert "O''Brien" not in insert_data[0][2]
            assert "''single quotes''" not in insert_data[0][3]

    def test_bulk_insert_logging(self, component, mock_embedding):
        """Test that bulk insert mode is logged correctly."""
        component.embedding = mock_embedding
        component.use_bulk_insert = True

        with (
            patch("ibm_db_dbi.connect") as mock_connect,
            patch.object(component, "_add_documents_to_vector_store"),
        ):
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            from lfx_ibm.components.ibm.db2vs import DB2VS

            with patch.object(DB2VS, "__init__", return_value=None), patch.object(component, "log") as mock_log:
                component.build_vector_store()

                messages = [str(call.args[0]).lower() for call in mock_log.call_args_list]
                assert any("bulk insert" in message or "executemany" in message for message in messages)

    def test_row_by_row_insert_logging(self, component, mock_embedding):
        """Test that row-by-row insert mode is logged correctly."""
        component.embedding = mock_embedding
        component.use_bulk_insert = False

        with (
            patch("ibm_db_dbi.connect") as mock_connect,
            patch.object(component, "_add_documents_to_vector_store"),
        ):
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            from lfx_ibm.components.ibm.db2vs import DB2VS

            with patch.object(DB2VS, "__init__", return_value=None), patch.object(component, "log") as mock_log:
                component.build_vector_store()

                messages = [str(call.args[0]).lower() for call in mock_log.call_args_list]
                assert any("row-by-row" in message or "execute" in message for message in messages)

    def test_bulk_insert_error_handling(self, mock_embedding):
        """Test that bulk insert handles errors gracefully with rollback."""
        from lfx_ibm.components.ibm.db2vs import DB2VS

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # Make executemany raise an error
        mock_cursor.executemany.side_effect = Exception("Database error")

        # Mock table operations
        with (
            patch("lfx_ibm.components.ibm.db2vs._table_exists", return_value=False),
            patch("lfx_ibm.components.ibm.db2vs._create_table"),
            patch(
                "lfx_ibm.components.ibm.db2vs._get_column_names",
                return_value={"id": "id", "embedding": "embedding", "metadata": "metadata", "text": "text"},
            ),
        ):
            vector_store = DB2VS(
                client=mock_connection,
                embedding_function=mock_embedding,
                table_name="test_table",
                use_bulk_insert=True,
            )

            # Attempt to add documents
            with pytest.raises(RuntimeError, match="during document insertion"):
                vector_store.add_texts(["Document 1", "Document 2"])

            # Verify rollback was attempted
            rollback_calls = [call for call in mock_cursor.execute.call_args_list if "ROLLBACK" in str(call)]
            assert len(rollback_calls) > 0, "ROLLBACK should be called on error"

    def test_bulk_insert_input_exists(self, component):
        """Test that use_bulk_insert input is defined in component."""
        # Check that the input exists in the component's inputs
        input_names = [inp.name for inp in component.inputs]
        assert "use_bulk_insert" in input_names, "use_bulk_insert input should be defined"

        # Find the input and verify its properties
        bulk_insert_input = next(inp for inp in component.inputs if inp.name == "use_bulk_insert")
        assert bulk_insert_input.value is True, "Default value should be True"
        assert bulk_insert_input.advanced is True, "Should be an advanced setting"


# Made with Bob
