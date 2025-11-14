from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from lfx.components.pinecone import PineconeVectorStoreComponent
from lfx.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping


@pytest.mark.api_key_required
class TestPineconeVectorStoreComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self) -> type[Any]:
        """Return the component class to test."""
        return PineconeVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self) -> dict[str, Any]:
        """Return the default kwargs for the component."""
        from lfx.components.openai.openai import OpenAIEmbeddingsComponent

        from tests.api_keys import get_openai_api_key

        try:
            api_key = get_openai_api_key()
        except ValueError:
            pytest.skip("OPENAI_API_KEY is not set")

        return {
            "embedding": OpenAIEmbeddingsComponent(openai_api_key=api_key).build_embeddings(),
            "index_name": "test-index",
            "namespace": "test-namespace",
            "pinecone_api_key": "test-pinecone-key",
            "text_key": "text",
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        return []

    def test_search_documents_with_namespace(
        self, component_class: type[PineconeVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test that search_documents properly passes namespace parameter.

        This test verifies the fix for issue #10512 where namespace wasn't being
        properly passed to Pinecone queries, resulting in zero results.
        """
        component: PineconeVectorStoreComponent = component_class().set(**default_kwargs)

        # Mock the Pinecone client and index
        mock_pinecone = MagicMock()
        mock_index = MagicMock()
        mock_pinecone.Index.return_value = mock_index

        # Mock query results
        mock_match = Mock()
        mock_match.metadata = {"text": "test result", "source": "test"}
        mock_results = Mock()
        mock_results.matches = [mock_match]
        mock_index.query.return_value = mock_results

        # Mock the vector store
        mock_vector_store = MagicMock()
        mock_vector_store._embedding.embed_query.return_value = [0.1] * 3072

        with (
            patch("lfx.components.pinecone.pinecone.Pinecone", return_value=mock_pinecone),
            patch.object(component, "build_vector_store", return_value=mock_vector_store),
        ):
            component.set(search_query="test query")
            results = component.search_documents()

            # Verify Pinecone was called correctly
            mock_pinecone.Index.assert_called_once_with("test-index")
            mock_index.query.assert_called_once()

            # Verify namespace was passed
            call_kwargs = mock_index.query.call_args[1]
            assert "namespace" in call_kwargs
            assert call_kwargs["namespace"] == "test-namespace"
            assert call_kwargs["top_k"] == 4
            assert call_kwargs["include_metadata"] is True

            # Verify results are returned
            assert len(results) == 1
            assert isinstance(results[0], Data)
            assert results[0].text == "test result"

    def test_search_documents_without_namespace(
        self, component_class: type[PineconeVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test that search_documents works without namespace."""
        # Remove namespace from kwargs
        default_kwargs.pop("namespace", None)
        component: PineconeVectorStoreComponent = component_class().set(**default_kwargs)

        # Mock the Pinecone client and index
        mock_pinecone = MagicMock()
        mock_index = MagicMock()
        mock_pinecone.Index.return_value = mock_index

        # Mock query results
        mock_match = Mock()
        mock_match.metadata = {"text": "test result"}
        mock_results = Mock()
        mock_results.matches = [mock_match]
        mock_index.query.return_value = mock_results

        # Mock the vector store
        mock_vector_store = MagicMock()
        mock_vector_store._embedding.embed_query.return_value = [0.1] * 3072

        with (
            patch("lfx.components.pinecone.pinecone.Pinecone", return_value=mock_pinecone),
            patch.object(component, "build_vector_store", return_value=mock_vector_store),
        ):
            component.set(search_query="test query")
            results = component.search_documents()

            # Verify namespace was NOT passed when not set
            call_kwargs = mock_index.query.call_args[1]
            assert "namespace" not in call_kwargs

            # Verify results are still returned
            assert len(results) == 1

    def test_search_documents_empty_query(
        self, component_class: type[PineconeVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test that empty query returns empty results."""
        component: PineconeVectorStoreComponent = component_class().set(**default_kwargs)
        component.set(search_query="")
        results = component.search_documents()
        assert results == []

    def test_search_documents_with_custom_text_key(
        self, component_class: type[PineconeVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test that custom text_key is properly used to extract content."""
        default_kwargs["text_key"] = "chunk_text"
        component: PineconeVectorStoreComponent = component_class().set(**default_kwargs)

        # Mock the Pinecone client and index
        mock_pinecone = MagicMock()
        mock_index = MagicMock()
        mock_pinecone.Index.return_value = mock_index

        # Mock query results with custom text key
        mock_match = Mock()
        mock_match.metadata = {"chunk_text": "custom text content", "source": "test"}
        mock_results = Mock()
        mock_results.matches = [mock_match]
        mock_index.query.return_value = mock_results

        # Mock the vector store
        mock_vector_store = MagicMock()
        mock_vector_store._embedding.embed_query.return_value = [0.1] * 3072

        with (
            patch("lfx.components.pinecone.pinecone.Pinecone", return_value=mock_pinecone),
            patch.object(component, "build_vector_store", return_value=mock_vector_store),
        ):
            component.set(search_query="test query")
            results = component.search_documents()

            # Verify the custom text_key was used
            assert len(results) == 1
            assert results[0].text == "custom text content"
