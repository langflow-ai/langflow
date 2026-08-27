"""LE-2352 / #6255: ingesting into the Cassandra vector store must not crash.

``build_vector_store`` called ``Cassandra.from_documents(..., batch_size=...)``.
``from_documents`` does not declare ``batch_size``, so it landed in ``**kwargs``
and was splatted into ``cls(...)`` -- i.e. ``Cassandra.__init__``, which accepts
only ``embedding, session, keyspace, table_name, ttl_seconds, body_index_options,
setup_mode, metadata_indexing``. Every run with anything wired to Ingest Data
died with::

    Cassandra.__init__() got an unexpected keyword argument 'batch_size'

``batch_size`` is a real parameter of ``Cassandra.add_texts`` (default 16), which
``add_documents`` forwards to, so the exposed component field has a correct home
and must keep working rather than being dropped.

Nothing above the storage layer is stubbed: ``cassio.init`` opens a real cluster
session and the cassio table writes rows, so those two are patched and everything
else -- the component, ``Cassandra.__init__``, ``add_documents`` -> ``add_texts`` --
runs as shipped. The bug cannot hide behind those patches either, since the
TypeError comes from binding arguments to ``__init__`` before its body runs.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langchain_community.vectorstores import Cassandra
from langchain_core.embeddings import Embeddings, FakeEmbeddings
from lfx.schema.data import Data
from lfx_datastax.components.cassandra.cassandra import CassandraVectorStoreComponent

MODULE = "lfx_datastax.components.cassandra.cassandra"
CASSIO_TABLE = "cassio.table.MetadataVectorCassandraTable"
BATCH_SIZE = 16


def _component(*, with_documents: bool, setup_mode: str = "Sync") -> CassandraVectorStoreComponent:
    component = CassandraVectorStoreComponent()
    component.database_ref = "127.0.0.1"
    component.username = "user"
    component.token = "token"  # noqa: S105
    component.keyspace = "test_keyspace"
    component.table_name = "test_table"
    component.ttl_seconds = 0
    component.batch_size = BATCH_SIZE
    component.cluster_kwargs = {}
    component.setup_mode = setup_mode
    component.enable_body_search = False
    component.embedding = MagicMock(spec=Embeddings)
    component.ingest_data = [Data(text="hello world")] if with_documents else []
    return component


@pytest.mark.parametrize(("document_count", "batch_size"), [(1, 16), (5, 2), (40, 16)])
def test_should_ingest_against_the_real_cassandra_implementation(document_count: int, batch_size: int):
    """The reported failure, checked end to end rather than against a stubbed class.

    Only the cassio storage table is patched -- the layer that genuinely needs a
    cluster. ``Cassandra.__init__``, ``add_documents`` and ``add_texts`` all run for
    real, so a mismatch anywhere in that chain still fails here, not just at the
    constructor where the reported TypeError happened to land.
    """
    component = _component(with_documents=False)
    component.batch_size = batch_size
    component.embedding = FakeEmbeddings(size=8)
    component.ingest_data = [Data(text=f"doc {i}") for i in range(document_count)]

    table = MagicMock()
    table.session = MagicMock()

    with patch("cassio.init"), patch(CASSIO_TABLE, MagicMock(return_value=table)):
        store = component.build_vector_store()

    assert isinstance(store, Cassandra)
    assert table.put_async.call_count == document_count, "not every document reached the store"


def test_should_pass_batch_size_to_add_documents():
    """The exposed field must keep its meaning, not be silently dropped."""
    component = _component(with_documents=True)
    table = MagicMock()

    with patch("cassio.init"), patch(f"{MODULE}.Cassandra", MagicMock(return_value=table)):
        result = component.build_vector_store()

    table.add_documents.assert_called_once()
    assert table.add_documents.call_args.kwargs["batch_size"] == BATCH_SIZE
    assert result is table


def test_should_ingest_every_document():
    component = _component(with_documents=True)
    table = MagicMock()

    with patch("cassio.init"), patch(f"{MODULE}.Cassandra", MagicMock(return_value=table)):
        component.build_vector_store()

    documents = table.add_documents.call_args.kwargs["documents"]
    assert len(documents) == 1
    assert documents[0].page_content == "hello world"


def test_should_not_add_documents_when_ingest_data_is_empty():
    """The search-only path was never broken and must stay untouched."""
    component = _component(with_documents=False)
    table = MagicMock()

    with patch("cassio.init"), patch(f"{MODULE}.Cassandra", MagicMock(return_value=table)) as cls:
        result = component.build_vector_store()

    table.add_documents.assert_not_called()
    assert "batch_size" not in cls.call_args.kwargs
    assert result is table


@pytest.mark.parametrize("setup_mode", ["Sync", "Async", "Off"])
def test_should_keep_the_ingest_path_on_synchronous_setup(setup_mode: str):
    """The ingest write is synchronous, so its table must not be built for async setup.

    ``SetupMode.ASYNC`` makes ``__init__`` hand cassio ``async_setup=True`` plus an
    un-awaited coroutine as the vector dimension, while ``add_documents``/``add_texts``
    are synchronous. ``from_documents`` never forwarded ``setup_mode`` either, so
    keeping SYNC here preserves the behaviour this fix is not meant to change.
    """
    from langchain_community.utilities.cassandra import SetupMode

    component = _component(with_documents=True, setup_mode=setup_mode)

    with patch("cassio.init"), patch(f"{MODULE}.Cassandra", MagicMock(return_value=MagicMock())) as cls:
        component.build_vector_store()

    assert cls.call_args.kwargs.get("setup_mode", SetupMode.SYNC) is SetupMode.SYNC
