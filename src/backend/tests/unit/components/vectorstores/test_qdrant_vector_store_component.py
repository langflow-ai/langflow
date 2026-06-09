"""Unit tests for the Qdrant vector store component.

Focuses on the stable, deterministic ID generation introduced for #12641
so re-ingesting the same content does not create duplicates.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from lfx.components.qdrant import QdrantVectorStoreComponent
from lfx.schema.data import Data


def _make_component(documents: list[Document]) -> QdrantVectorStoreComponent:
    return QdrantVectorStoreComponent().set(
        collection_name="test_collection",
        embedding=MagicMock(spec=Embeddings),
        ingest_data=[Data(text=doc.page_content, data=doc.metadata) for doc in documents],
    )


def _captured_ids(documents: list[Document]) -> list[str]:
    """Run build_vector_store with QdrantVectorStore.from_documents patched and return the ids passed in."""
    component = _make_component(documents)

    captured: dict[str, list[str]] = {}

    def fake_from_documents(_docs, *, embedding, ids, **_kwargs):  # noqa: ARG001
        captured["ids"] = ids
        return MagicMock()

    with patch("lfx.components.qdrant.qdrant.QdrantVectorStore.from_documents", side_effect=fake_from_documents):
        component.build_vector_store()

    return captured["ids"]


def test_qdrant_ids_are_deterministic_uuid5() -> None:
    """Same content + metadata must always produce the same UUID."""
    docs = [Document(page_content="hello world", metadata={"source": "a.txt", "page": 1})]

    first = _captured_ids(docs)
    second = _captured_ids(docs)

    assert first == second
    # UUID5 strings: 36 chars including hyphens, version nibble == '5'.
    parsed = uuid.UUID(first[0])
    assert parsed.version == 5


def test_qdrant_ids_are_metadata_order_independent() -> None:
    """Two docs with identical content and metadata in different insertion order share an ID."""
    doc_a = Document(page_content="same text", metadata={"a": 1, "b": 2, "nested": {"x": 1, "y": 2}})
    doc_b = Document(page_content="same text", metadata={"nested": {"y": 2, "x": 1}, "b": 2, "a": 1})

    ids = _captured_ids([doc_a, doc_b])

    assert ids[0] == ids[1]


def test_qdrant_ids_differ_for_different_content() -> None:
    docs = [
        Document(page_content="first", metadata={"source": "a"}),
        Document(page_content="second", metadata={"source": "a"}),
    ]

    ids = _captured_ids(docs)

    assert ids[0] != ids[1]


def test_qdrant_ids_handle_non_primitive_metadata() -> None:
    """Non-primitive metadata (datetime, Decimal) must serialize without raising and stay deterministic."""
    ts = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    docs = [Document(page_content="payload", metadata={"ts": ts, "price": Decimal("9.99")})]

    first = _captured_ids(docs)
    second = _captured_ids(docs)

    assert first == second
    uuid.UUID(first[0])  # raises if not a valid UUID
