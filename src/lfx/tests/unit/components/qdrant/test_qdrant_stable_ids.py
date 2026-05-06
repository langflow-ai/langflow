"""Regression tests for deterministic Qdrant document IDs (issue #12641).

Re-ingesting the same documents through the Qdrant component must produce
the same point IDs so that Qdrant upserts in place instead of creating
duplicate points.
"""

import uuid

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
        result = _generate_stable_id("Hello world", {"source": "test.txt"})
        # Should not raise
        uuid.UUID(result)

    def test_id_is_stable_across_runs_golden_value(self):
        """Pin the exact UUID for a known input to catch silent encoding regressions.

        If anyone ever changes the namespace, separators, sort_keys flag, or
        payload shape in ``_generate_stable_id``, this assertion fails and we
        notice BEFORE shipping a change that would silently break every
        existing user's Qdrant collection (re-ingesting their docs would
        suddenly create new points alongside the old).
        """
        result = _generate_stable_id("Hello world", {"source": "test.txt"})
        # Recompute locally if you intentionally change the algorithm.
        assert result == "0ccd3351-1f5c-5b67-9416-a7c1715bb188"

    def test_metadata_with_pipe_and_equals_chars_does_not_collide(self):
        """Metadata values with ``|`` or ``=`` must not create collisions.

        Guards against ambiguity in the payload encoding (regression for the
        original ad-hoc ``f"{k}={v}"`` join).
        """
        # These two docs would produce the same string under naive
        # ``content|k=v|...`` concatenation but must produce DIFFERENT IDs.
        id_a = _generate_stable_id("x", {"a": "b|c=d"})
        id_b = _generate_stable_id("x|a=b", {"c": "d"})
        assert id_a != id_b

        # Same input → same ID, even with special characters.
        id_c = _generate_stable_id("x", {"a": "b|c=d"})
        assert id_a == id_c

    def test_nested_metadata_is_order_independent(self):
        """Nested dict insertion order must not change the ID.

        Canonical JSON serialization with sort_keys handles this recursively.
        """
        meta1 = {"outer": {"x": 1, "y": 2}, "tag": "a"}
        meta2 = {"tag": "a", "outer": {"y": 2, "x": 1}}

        assert _generate_stable_id("doc", meta1) == _generate_stable_id("doc", meta2)

    def test_nested_metadata_different_values_produce_different_ids(self):
        """Different nested values must yield different IDs."""
        meta1 = {"outer": {"x": 1, "y": 2}}
        meta2 = {"outer": {"x": 1, "y": 3}}

        assert _generate_stable_id("doc", meta1) != _generate_stable_id("doc", meta2)

    def test_special_chars_in_content_and_nested_metadata(self):
        """Nested metadata + special characters must still yield stable IDs.

        Combination case verifying canonical encoding handles both at once.
        """
        import uuid

        meta = {"section": {"title": "a|b", "n": 1}, "key=with=equals": "val|with|pipes"}
        result = _generate_stable_id('content with "quotes" and |pipes|', meta)

        # Stable across calls.
        assert result == _generate_stable_id('content with "quotes" and |pipes|', meta)
        # Valid UUID.
        uuid.UUID(result)
