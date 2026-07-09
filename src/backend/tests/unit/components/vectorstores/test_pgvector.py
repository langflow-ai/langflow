from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.embeddings import Embeddings
from lfx.components.pgvector import PGVectorStoreComponent, PGVectorWriteComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from sqlalchemy.exc import DataError


def test_pgvector_read_keeps_original_component_name_and_inputs() -> None:
    inputs = {input_.name: input_ for input_ in PGVectorStoreComponent.inputs}

    assert PGVectorStoreComponent.display_name == "PGVector"
    assert "ingest_data" in inputs
    assert "search_query" in inputs
    assert inputs["collection_name"].display_name == "Collection Name"


def test_pgvector_write_batches_documents() -> None:
    component = PGVectorWriteComponent().set(
        pg_server_url="postgresql://user:pass@localhost:5432/db",
        collection_name="documents",
        embedding=MagicMock(spec=Embeddings),
        ingest_data=[Data(data={"text": f"document {index}", "source": "test"}) for index in range(5)],
        embedding_field="text",
        batch_size=2,
    )
    vector_store = MagicMock()
    vector_store.add_documents.side_effect = [["id-1", "id-2"], ["id-3", "id-4"], ["id-5"]]

    with patch(
        "lfx.components.pgvector.pgvector_write.PGVector.from_existing_index",
        return_value=vector_store,
    ) as pgvector:
        summary = component.write_documents()

    pgvector.assert_called_once_with(
        embedding=component.embedding,
        collection_name="documents",
        connection_string="postgresql://user:pass@localhost:5432/db",
    )
    assert isinstance(summary, DataFrame)
    assert summary.iloc[0].to_dict() == {
        "collection_name": "documents",
        "documents_written": 5,
        "batches_written": 3,
        "batch_size": 2,
        "embedding_field": "text",
        "metadata_fields": "",
        "storage_schema": "langchain_pgvector",
        "embedding_table": "langchain_pg_embedding",
        "collection_table": "langchain_pg_collection",
        "creates_schema_if_missing": True,
        "ids_returned": 5,
    }
    assert vector_store.add_documents.call_count == 3
    batch_lengths = [len(call.args[0]) for call in vector_store.add_documents.call_args_list]
    assert batch_lengths == [2, 2, 1]


def test_pgvector_write_accepts_dataframe_input() -> None:
    component = PGVectorWriteComponent().set(
        pg_server_url="postgresql://user:pass@localhost:5432/db",
        collection_name="documents",
        embedding=MagicMock(spec=Embeddings),
        ingest_data=DataFrame([{"text": "one"}, {"text": "two"}]),
        embedding_field="text",
        batch_size=10,
    )
    vector_store = MagicMock()
    vector_store.add_documents.return_value = ["id-1", "id-2"]

    with patch("lfx.components.pgvector.pgvector_write.PGVector.from_existing_index", return_value=vector_store):
        summary = component.write_documents()

    assert summary.iloc[0]["documents_written"] == 2
    batch = vector_store.add_documents.call_args.args[0]
    assert [document.page_content for document in batch] == ["one", "two"]


def test_pgvector_write_labels_collection_name_as_collection() -> None:
    inputs = {input_.name: input_ for input_ in PGVectorWriteComponent.inputs}

    assert inputs["collection_name"].display_name == "Collection Name"
    assert "langchain_pg_embedding" in inputs["collection_name"].info


def test_pgvector_write_uses_selected_embedding_and_metadata_fields() -> None:
    component = PGVectorWriteComponent().set(
        pg_server_url="postgresql://user:pass@localhost:5432/db",
        collection_name="documents",
        embedding=MagicMock(spec=Embeddings),
        ingest_data=DataFrame(
            [
                {"body": "one", "title": "First", "source": "a.txt", "ignored": "skip"},
                {"body": "two", "title": "Second", "source": "b.txt", "ignored": "skip"},
            ]
        ),
        embedding_field="body",
        metadata_fields="title, source",
        batch_size=10,
    )
    vector_store = MagicMock()
    vector_store.add_documents.return_value = ["id-1", "id-2"]

    with patch("lfx.components.pgvector.pgvector_write.PGVector.from_existing_index", return_value=vector_store):
        summary = component.write_documents()

    batch = vector_store.add_documents.call_args.args[0]
    assert [document.page_content for document in batch] == ["one", "two"]
    assert batch[0].metadata == {"title": "First", "source": "a.txt"}
    assert batch[1].metadata == {"title": "Second", "source": "b.txt"}
    assert summary.iloc[0]["embedding_field"] == "body"
    assert summary.iloc[0]["metadata_fields"] == "title, source"


def test_pgvector_write_rejects_missing_metadata_fields() -> None:
    component = PGVectorWriteComponent().set(
        pg_server_url="postgresql://user:pass@localhost:5432/db",
        collection_name="documents",
        embedding=MagicMock(spec=Embeddings),
        ingest_data=DataFrame([{"body": "one", "title": "First"}]),
        embedding_field="body",
        metadata_fields="title, source",
        batch_size=10,
    )

    with pytest.raises(ValueError, match="Metadata field\\(s\\) not found"):
        component.write_documents()


def test_pgvector_write_requires_existing_embedding_field() -> None:
    component = PGVectorWriteComponent().set(
        pg_server_url="postgresql://user:pass@localhost:5432/db",
        collection_name="documents",
        embedding=MagicMock(spec=Embeddings),
        ingest_data=[Data(data={"text": "document"})],
        embedding_field="body",
        batch_size=2,
    )

    with pytest.raises(ValueError, match="Embedding Field 'body'"):
        component.write_documents()


def test_pgvector_write_requires_documents() -> None:
    component = PGVectorWriteComponent().set(
        pg_server_url="postgresql://user:pass@localhost:5432/db",
        collection_name="documents",
        embedding=MagicMock(spec=Embeddings),
        ingest_data=[],
        embedding_field="text",
        batch_size=2,
    )

    with pytest.raises(ValueError, match="No documents"):
        component.write_documents()


def test_pgvector_write_requires_positive_batch_size() -> None:
    component = PGVectorWriteComponent().set(
        pg_server_url="postgresql://user:pass@localhost:5432/db",
        collection_name="documents",
        embedding=MagicMock(spec=Embeddings),
        ingest_data=[Data(data={"text": "document"})],
        embedding_field="text",
        batch_size=0,
    )

    with pytest.raises(ValueError, match="Batch Size"):
        component.write_documents()


def test_pgvector_write_reports_incomplete_embedding_response() -> None:
    component = PGVectorWriteComponent()
    vector_store = MagicMock()
    vector_store.add_documents.side_effect = IndexError("list index out of range")

    with pytest.raises(ValueError, match="fewer embeddings than requested"):
        component._add_documents(vector_store, [])


def test_pgvector_write_reports_empty_embedding_vector() -> None:
    component = PGVectorWriteComponent()
    vector_store = MagicMock()
    vector_store.add_documents.side_effect = DataError(
        "statement",
        {},
        Exception("vector must have at least 1 dimension"),
    )

    with pytest.raises(ValueError, match="empty embedding vector"):
        component._add_documents(vector_store, [])
