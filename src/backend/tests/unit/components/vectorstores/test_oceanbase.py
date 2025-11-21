"""Tests for the OceanBase Vector Store component."""

import builtins
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_community.embeddings.fake import DeterministicFakeEmbedding
from langchain_core.documents import Document
from lfx.components.oceanbase import OceanBaseVectorStoreComponent
from lfx.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient


class TestOceanBaseVectorStoreComponent(ComponentTestBaseWithoutClient):
    """Test suite for the OceanBaseVectorStoreComponent class."""

    @pytest.fixture
    def component_class(self) -> type[Any]:
        """Return the component class to test."""
        return OceanBaseVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self) -> dict[str, Any]:
        """Return the default kwargs for the component."""
        return {
            "host": "127.0.0.1",
            "port": 2881,
            "database": "test",
            "table": "langchain_vector",
            "username": "root@test",
            "password": "test_password",
            "embedding": DeterministicFakeEmbedding(size=10),
            "index_type": "HNSW",
            "vidx_metric_type": "l2",
        }

    @pytest.fixture
    def file_names_mapping(self) -> list:
        """Return the file names mapping for different versions."""
        return []

    @patch("lfx.components.oceanbase.oceanbase.OceanbaseVectorStore")
    def test_build_vector_store_with_documents(
        self,
        mock_vector_store_class: MagicMock,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test building vector store with documents."""
        # Mock pymysql in sys.modules
        mock_pymysql = MagicMock()
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_pymysql.connect.return_value = mock_connection

        sys.modules["pymysql"] = mock_pymysql

        try:
            # Mock OceanbaseVectorStore
            mock_vector_store_instance = MagicMock()
            mock_vector_store_class.from_texts.return_value = mock_vector_store_instance

            # Create test data
            test_data = [Data(text="test document 1"), Data(text="test document 2")]
            default_kwargs["ingest_data"] = test_data

            component = component_class().set(**default_kwargs)
            vector_store = component.build_vector_store()

            # Verify connection was tested
            assert mock_pymysql.connect.called
            assert mock_cursor.execute.called
            assert mock_cursor.close.called
            assert mock_connection.close.called

            # Verify vector store was created with documents
            mock_vector_store_class.from_texts.assert_called_once()
            call_kwargs = mock_vector_store_class.from_texts.call_args
            assert call_kwargs is not None
            assert len(call_kwargs[1]["texts"]) == 2
            assert vector_store == mock_vector_store_instance
        finally:
            # Clean up
            if "pymysql" in sys.modules and not hasattr(sys.modules["pymysql"], "connect"):
                del sys.modules["pymysql"]

    @patch("lfx.components.oceanbase.oceanbase.OceanbaseVectorStore")
    def test_build_vector_store_without_documents(
        self,
        mock_vector_store_class: MagicMock,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test building vector store without documents."""
        # Mock pymysql in sys.modules
        mock_pymysql = MagicMock()
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_pymysql.connect.return_value = mock_connection

        sys.modules["pymysql"] = mock_pymysql

        try:
            # Mock OceanbaseVectorStore
            mock_vector_store_instance = MagicMock()
            mock_vector_store_class.return_value = mock_vector_store_instance

            component = component_class().set(**default_kwargs)
            vector_store = component.build_vector_store()

            # Verify vector store was created without documents
            mock_vector_store_class.assert_called_once()
            assert vector_store == mock_vector_store_instance
        finally:
            # Clean up
            if "pymysql" in sys.modules and not hasattr(sys.modules["pymysql"], "connect"):
                del sys.modules["pymysql"]

    def test_build_vector_store_connection_error(
        self,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test error handling when connection fails."""
        # Mock pymysql in sys.modules with connection error
        mock_pymysql = MagicMock()
        mock_pymysql.connect.side_effect = Exception("Connection failed")

        sys.modules["pymysql"] = mock_pymysql

        try:
            component = component_class().set(**default_kwargs)

            with pytest.raises(ValueError, match="Failed to connect to OceanBase"):
                component.build_vector_store()
        finally:
            # Clean up
            if "pymysql" in sys.modules and not hasattr(sys.modules["pymysql"], "connect"):
                del sys.modules["pymysql"]

    def test_build_vector_store_missing_pymysql(
        self,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test error handling when pymysql is not installed."""
        # Mock the import to raise ImportError
        original_import = builtins.__import__
        error_msg = "No module named 'pymysql'"

        def import_side_effect(name, *args, **kwargs):
            if name == "pymysql":
                raise ImportError(error_msg)
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_side_effect):
            component = component_class().set(**default_kwargs)

            with pytest.raises(ImportError, match="Failed to import MySQL dependencies"):
                component.build_vector_store()

    def test_get_index_params_hnsw(
        self,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test getting index parameters for HNSW index type."""
        default_kwargs["index_type"] = "HNSW"
        default_kwargs["M"] = 16
        default_kwargs["efConstruction"] = 200

        component = component_class().set(**default_kwargs)
        params = component._get_index_params()

        assert params == {"M": 16, "efConstruction": 200}

    def test_get_index_params_ivf(
        self,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test getting index parameters for IVF index type."""
        default_kwargs["index_type"] = "IVF"
        default_kwargs["nlist"] = 128

        component = component_class().set(**default_kwargs)
        params = component._get_index_params()

        assert params == {"nlist": 128}

    def test_get_index_params_ivf_pq(
        self,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test getting index parameters for IVF_PQ index type."""
        default_kwargs["index_type"] = "IVF_PQ"
        default_kwargs["nlist"] = 128
        default_kwargs["m"] = 3

        component = component_class().set(**default_kwargs)
        params = component._get_index_params()

        assert params == {"nlist": 128, "m": 3}

    def test_get_index_params_flat(
        self,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test getting index parameters for FLAT index type."""
        default_kwargs["index_type"] = "FLAT"

        component = component_class().set(**default_kwargs)
        params = component._get_index_params()

        assert params == {}

    def test_get_search_params_hnsw(
        self,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test getting search parameters for HNSW index type."""
        default_kwargs["index_type"] = "HNSW"
        default_kwargs["efSearch"] = 64

        component = component_class().set(**default_kwargs)
        params = component._get_search_params()

        assert params == {"efSearch": 64}

    def test_get_search_params_ivf(
        self,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test getting search parameters for IVF index type."""
        default_kwargs["index_type"] = "IVF"
        default_kwargs["nprobe"] = 10

        component = component_class().set(**default_kwargs)
        params = component._get_search_params()

        assert params == {"nprobe": 10}

    @patch("lfx.components.oceanbase.oceanbase.OceanbaseVectorStore")
    def test_search_documents(
        self,
        mock_vector_store_class: MagicMock,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test searching documents."""
        # Mock pymysql in sys.modules
        mock_pymysql = MagicMock()
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_pymysql.connect.return_value = mock_connection

        sys.modules["pymysql"] = mock_pymysql

        try:
            # Mock vector store and retriever
            mock_vector_store_instance = MagicMock()
            mock_retriever = MagicMock()
            mock_vector_store_instance.as_retriever.return_value = mock_retriever

            # Mock search results
            mock_docs = [
                Document(page_content="test document 1", metadata={}),
                Document(page_content="test document 2", metadata={}),
            ]
            mock_retriever.invoke.return_value = mock_docs

            mock_vector_store_class.return_value = mock_vector_store_instance

            component = component_class().set(**default_kwargs)
            component.set(search_query="test query", number_of_results=2)

            results = component.search_documents()

            assert len(results) == 2
            assert all(isinstance(result, Data) for result in results)
            mock_retriever.invoke.assert_called_once_with("test query")
        finally:
            # Clean up
            if "pymysql" in sys.modules and not hasattr(sys.modules["pymysql"], "connect"):
                del sys.modules["pymysql"]

    @patch("lfx.components.oceanbase.oceanbase.OceanbaseVectorStore")
    def test_search_documents_with_score_threshold(
        self,
        mock_vector_store_class: MagicMock,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test searching documents with score threshold."""
        # Mock pymysql in sys.modules
        mock_pymysql = MagicMock()
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_pymysql.connect.return_value = mock_connection

        sys.modules["pymysql"] = mock_pymysql

        try:
            # Mock vector store and retriever
            mock_vector_store_instance = MagicMock()
            mock_retriever = MagicMock()
            mock_vector_store_instance.as_retriever.return_value = mock_retriever

            mock_docs = [Document(page_content="test document", metadata={})]
            mock_retriever.invoke.return_value = mock_docs

            mock_vector_store_class.return_value = mock_vector_store_instance

            component = component_class().set(**default_kwargs)
            component.set(search_query="test query", score_threshold=0.5, number_of_results=10)

            results = component.search_documents()

            assert len(results) == 1
            # Verify as_retriever was called with score_threshold
            mock_vector_store_instance.as_retriever.assert_called_once()
            call_kwargs = mock_vector_store_instance.as_retriever.call_args
            assert call_kwargs is not None
            assert call_kwargs[1]["search_type"] == "similarity_score_threshold"
            assert call_kwargs[1]["search_kwargs"]["score_threshold"] == 0.5
        finally:
            # Clean up
            if "pymysql" in sys.modules and not hasattr(sys.modules["pymysql"], "connect"):
                del sys.modules["pymysql"]

    @patch("lfx.components.oceanbase.oceanbase.OceanbaseVectorStore")
    def test_search_documents_empty_query(
        self,
        mock_vector_store_class: MagicMock,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test searching with empty query returns empty list."""
        # Mock pymysql in sys.modules
        mock_pymysql = MagicMock()
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_pymysql.connect.return_value = mock_connection

        sys.modules["pymysql"] = mock_pymysql

        try:
            mock_vector_store_instance = MagicMock()
            mock_vector_store_class.return_value = mock_vector_store_instance

            component = component_class().set(**default_kwargs)
            component.set(search_query="")

            results = component.search_documents()

            assert results == []
            mock_vector_store_instance.as_retriever.assert_not_called()
        finally:
            # Clean up
            if "pymysql" in sys.modules and not hasattr(sys.modules["pymysql"], "connect"):
                del sys.modules["pymysql"]

    @patch("lfx.components.oceanbase.oceanbase.OceanbaseVectorStore")
    def test_search_documents_invalid_score_threshold(
        self,
        mock_vector_store_class: MagicMock,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test searching with invalid score threshold."""
        # Mock pymysql in sys.modules
        mock_pymysql = MagicMock()
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_pymysql.connect.return_value = mock_connection

        sys.modules["pymysql"] = mock_pymysql

        try:
            # Mock vector store and retriever
            mock_vector_store_instance = MagicMock()
            mock_retriever = MagicMock()
            mock_vector_store_instance.as_retriever.return_value = mock_retriever

            mock_docs = [Document(page_content="test document", metadata={})]
            mock_retriever.invoke.return_value = mock_docs

            mock_vector_store_class.return_value = mock_vector_store_instance

            component = component_class().set(**default_kwargs)
            # Set score_threshold to None (invalid/empty value)
            component.set(search_query="test query", score_threshold=None, number_of_results=10)

            results = component.search_documents()

            # Should still work, but score_threshold should be None
            assert len(results) == 1
            # Verify as_retriever was called without score_threshold
            call_kwargs = mock_vector_store_instance.as_retriever.call_args
            assert call_kwargs is not None
            assert "score_threshold" not in call_kwargs[1].get("search_kwargs", {})
        finally:
            # Clean up
            if "pymysql" in sys.modules and not hasattr(sys.modules["pymysql"], "connect"):
                del sys.modules["pymysql"]

    def test_parameter_validation(
        self,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test parameter validation and default values."""
        component = component_class().set(**default_kwargs)

        # Test default values
        assert component.primary_field == "id"
        assert component.vector_field == "embedding"
        assert component.text_field == "document"
        assert component.metadata_field == "metadata"
        assert component.vidx_name == "vidx"
        assert component.number_of_results == 10
        assert component.score_threshold == 0.0

    def test_index_type_parameter_handling(
        self,
        component_class: type[OceanBaseVectorStoreComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test different index type parameter handling."""
        # Test HNSW_SQ
        default_kwargs["index_type"] = "HNSW_SQ"
        component = component_class().set(**default_kwargs)
        params = component._get_index_params()
        assert "M" in params
        assert "efConstruction" in params

        # Test IVF_SQ
        default_kwargs["index_type"] = "IVF_SQ"
        component = component_class().set(**default_kwargs)
        params = component._get_index_params()
        assert "nlist" in params
