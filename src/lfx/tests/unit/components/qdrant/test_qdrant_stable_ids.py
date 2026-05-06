"""Regression tests for deterministic Qdrant document IDs (issue #12641).

Re-ingesting the same documents through the Qdrant component must produce
the same point IDs so that Qdrant upserts in place instead of creating
duplicate points.
"""

import pytest

pytest.importorskip("langchain_community")

from langchain_core.documents import Document
from lfx.components.qdrant.qdrant import _generate_stable_id


class TestQdrantStableIds:
    def test_same_content_and_metadata_produces_same_id(self):
        doc1 = Document(page_content="Hello world", metadata={"source": "test.txt", "page": 1})
        doc2 = Document(page_content="Hello world", metadata={"source": "test.txt", "page": 1})

        assert _generate_stable_id(doc1.page_content, doc1.metadata) == _generate_stable_id(
            doc2.page_content, doc2.metadata
        )

    def test_metadata_dict_order_does_not_affect_id(self):
        doc1 = Document(page_content="Hello world", metadata={"source": "test.txt", "page": 1})
        doc2 = Document(page_content="Hello world", metadata={"page": 1, "source": "test.txt"})

        assert _generate_stable_id(doc1.page_content, doc1.metadata) == _generate_stable_id(
            doc2.page_content, doc2.metadata
        )

    def test_different_metadata_produces_different_id(self):
        doc1 = Document(page_content="Hello world", metadata={"source": "test.txt", "page": 1})
        doc2 = Document(page_content="Hello world", metadata={"source": "test.txt", "page": 2})

        assert _generate_stable_id(doc1.page_content, doc1.metadata) != _generate_stable_id(
            doc2.page_content, doc2.metadata
        )

    def test_different_content_produces_different_id(self):
        doc1 = Document(page_content="Hello world", metadata={"source": "test.txt"})
        doc2 = Document(page_content="Goodbye world", metadata={"source": "test.txt"})

        assert _generate_stable_id(doc1.page_content, doc1.metadata) != _generate_stable_id(
            doc2.page_content, doc2.metadata
        )

    def test_empty_metadata_is_supported(self):
        id1 = _generate_stable_id("Hello world", {})
        id2 = _generate_stable_id("Hello world", {})

        assert id1 == id2

    def test_id_is_valid_uuid_string(self):
        import uuid

        result = _generate_stable_id("Hello world", {"source": "test.txt"})
        # Should not raise
        uuid.UUID(result)
