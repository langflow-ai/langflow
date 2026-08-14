"""Unit tests for the Cassandra vector store component.

Regression coverage for #6255: `Cassandra.from_documents()` forwarded `batch_size`
straight into `Cassandra.__init__()`, which doesn't accept it, raising
`TypeError: Cassandra.__init__() got an unexpected keyword argument 'batch_size'`
any time documents were ingested.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from langchain_core.embeddings import Embeddings
from lfx.components.cassandra.cassandra import CassandraVectorStoreComponent
from lfx.schema.data import Data


def _component(*, with_documents: bool, setup_mode: str = "Sync") -> CassandraVectorStoreComponent:
    ingest_data = [Data(text="hello world")] if with_documents else []
    return CassandraVectorStoreComponent().set(
        database_ref="127.0.0.1",
        username="user",
        token="token",  # noqa: S106
        keyspace="test_keyspace",
        table_name="test_table",
        batch_size=16,
        setup_mode=setup_mode,
        embedding=MagicMock(spec=Embeddings),
        ingest_data=ingest_data,
    )


def test_build_vector_store_does_not_pass_batch_size_to_constructor() -> None:
    """`batch_size` must never reach `Cassandra.__init__`, only `add_documents`."""
    component = _component(with_documents=True)

    mock_table = MagicMock()
    mock_cassandra_cls = MagicMock(return_value=mock_table)

    with (
        patch("cassio.init"),
        patch("lfx.components.cassandra.cassandra.Cassandra", mock_cassandra_cls),
    ):
        result = component.build_vector_store()

    # The constructor call must not include batch_size.
    _, init_kwargs = mock_cassandra_cls.call_args
    assert "batch_size" not in init_kwargs

    # batch_size belongs to add_documents instead.
    mock_table.add_documents.assert_called_once()
    add_documents_args, add_documents_kwargs = mock_table.add_documents.call_args
    assert add_documents_kwargs["batch_size"] == 16
    assert len(add_documents_args[0]) == 1

    assert result is mock_table


def test_build_vector_store_respects_setup_mode_when_documents_present() -> None:
    """setup_mode must reach the constructor even when documents are ingested (secondary bug)."""
    from langchain_community.utilities.cassandra import SetupMode

    component = _component(with_documents=True, setup_mode="Off")

    mock_cassandra_cls = MagicMock(return_value=MagicMock())

    with (
        patch("cassio.init"),
        patch("lfx.components.cassandra.cassandra.Cassandra", mock_cassandra_cls),
    ):
        component.build_vector_store()

    _, init_kwargs = mock_cassandra_cls.call_args
    assert init_kwargs["setup_mode"] == SetupMode.OFF


def test_build_vector_store_without_documents_is_unaffected() -> None:
    """The no-documents path (already correct) must keep working exactly as before."""
    component = _component(with_documents=False)

    mock_table = MagicMock()
    mock_cassandra_cls = MagicMock(return_value=mock_table)

    with (
        patch("cassio.init"),
        patch("lfx.components.cassandra.cassandra.Cassandra", mock_cassandra_cls),
    ):
        result = component.build_vector_store()

    mock_table.add_documents.assert_not_called()
    _, init_kwargs = mock_cassandra_cls.call_args
    assert "batch_size" not in init_kwargs
    assert result is mock_table


def test_build_vector_store_with_real_cassandra_signature_does_not_raise_typeerror() -> None:
    """End-to-end regression check against the real langchain_community Cassandra signature."""
    from langchain_community.vectorstores import Cassandra

    component = _component(with_documents=True)

    with (
        patch("cassio.init"),
        patch.object(Cassandra, "__init__", return_value=None) as mock_init,
        patch.object(Cassandra, "add_documents", return_value=None) as mock_add_documents,
    ):
        component.build_vector_store()

    mock_init.assert_called_once()
    assert "batch_size" not in mock_init.call_args.kwargs
    mock_add_documents.assert_called_once()
    assert mock_add_documents.call_args.kwargs["batch_size"] == 16
