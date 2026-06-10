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
from qdrant_client.models import Distance


def _make_component(documents: list[Document]) -> QdrantVectorStoreComponent:
    embedding = MagicMock(spec=Embeddings)
    embedding.embed_query.return_value = [0.1, 0.2, 0.3]
    return QdrantVectorStoreComponent().set(
        collection_name="test_collection",
        embedding=embedding,
        ingest_data=[Data(text=doc.page_content, data=doc.metadata) for doc in documents],
    )


def _captured_ids(documents: list[Document]) -> list[str]:
    """Run build_vector_store and return the ids passed to add_documents."""
    component = _make_component(documents)

    captured: dict[str, list[str]] = {}
    client = MagicMock()
    client.collection_exists.return_value = True
    qdrant = MagicMock()

    def fake_add_documents(*, documents, ids):  # noqa: ARG001
        captured["ids"] = ids

    qdrant.add_documents.side_effect = fake_add_documents

    with (
        patch("lfx.components.qdrant.qdrant.QdrantClient", return_value=client),
        patch("lfx.components.qdrant.qdrant.QdrantVectorStore", return_value=qdrant),
    ):
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


def test_qdrant_creates_missing_collection_from_embedding_dimension() -> None:
    component = _make_component([]).set(distance_func="Dot Product")
    client = MagicMock()
    client.collection_exists.return_value = False
    qdrant = MagicMock()

    with (
        patch("lfx.components.qdrant.qdrant.QdrantClient", return_value=client),
        patch("lfx.components.qdrant.qdrant.QdrantVectorStore", return_value=qdrant),
    ):
        vector_store = component.build_vector_store()

    assert vector_store is qdrant
    client.create_collection.assert_called_once()
    create_kwargs = client.create_collection.call_args.kwargs
    assert create_kwargs["collection_name"] == "test_collection"
    assert create_kwargs["vectors_config"].size == 3
    assert create_kwargs["vectors_config"].distance == Distance.DOT
