"""Regression tests for PineconeVectorStoreComponent."""

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("langchain_core")
pytest.importorskip("numpy")

from lfx.components.pinecone.pinecone import PineconeVectorStoreComponent


class TestPineconeNamespacePassthrough:
    """Regression test: namespace must be forwarded to similarity_search.

    Issue #9188: search_documents() called similarity_search() without the
    namespace argument, causing searches to always hit the default namespace
    regardless of what the user configured.
    """

    def _make_component(self, namespace: str = "my-ns") -> PineconeVectorStoreComponent:
        comp = PineconeVectorStoreComponent()
        comp.search_query = "test query"
        comp.number_of_results = 4
        comp.namespace = namespace
        return comp

    def test_namespace_forwarded_to_similarity_search(self):
        """similarity_search must receive namespace=self.namespace."""
        comp = self._make_component(namespace="prod-ns")

        mock_store = MagicMock()
        mock_store.similarity_search.return_value = []

        with patch.object(comp, "build_vector_store", return_value=mock_store):
            comp.search_documents()

        mock_store.similarity_search.assert_called_once_with(
            query="test query",
            k=4,
            namespace="prod-ns",
        )

    def test_empty_namespace_forwarded(self):
        """An empty namespace string should still be passed through."""
        comp = self._make_component(namespace="")

        mock_store = MagicMock()
        mock_store.similarity_search.return_value = []

        with patch.object(comp, "build_vector_store", return_value=mock_store):
            comp.search_documents()

        _call_kwargs = mock_store.similarity_search.call_args.kwargs
        assert "namespace" in _call_kwargs
        assert _call_kwargs["namespace"] == ""
