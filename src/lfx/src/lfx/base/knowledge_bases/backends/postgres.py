"""Postgres (pgvector) vector-store backend.

Wraps ``langchain_postgres.PGVector``. Connection string comes from
a Langflow variable so the ``backend_config`` dict stays free of raw
credentials.

``backend_config`` shape::

    {
        "connection_uri_variable": "POSTGRES_CONNECTION_URL",
        "collection_name": "my_kb",
    }

``collection_name`` becomes the logical partition key inside the
``langchain_pg_embedding`` table that ``langchain_postgres`` manages
— one Postgres schema can host many KBs without colliding.
"""

from __future__ import annotations

import asyncio
import queue as sync_queue
from typing import TYPE_CHECKING, Any

from lfx.base.knowledge_bases.backends.base import (
    BackendType,
    BaseVectorStoreBackend,
    IngestedDocument,
)
from lfx.log.logger import logger

# Column count in the ``document, metadata[, embedding]`` projection
# below. The ``> 2`` check guards the optional embedding column.
_ROWS_WITH_EMBEDDING_COLS = 3

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langchain_core.vectorstores import VectorStore


DEFAULT_CONNECTION_URI_VARIABLE = "POSTGRES_CONNECTION_URL"


class PostgresBackend(BaseVectorStoreBackend):
    """pgvector-backed Langflow KB via ``langchain_postgres``."""

    backend_type = BackendType.POSTGRES

    def _required(self, key: str) -> str:
        value = self.backend_config.get(key)
        if not value:
            msg = f"PostgresBackend requires '{key}' in backend_config."
            raise ValueError(msg)
        return str(value)

    async def _resolve_secrets(self) -> None:
        """Resolve the Postgres URL via Langflow's variable_service."""
        variable_name = self.backend_config.get("connection_uri_variable") or DEFAULT_CONNECTION_URI_VARIABLE
        value = await self.resolve_secret(variable_name)
        if not value:
            msg = (
                f"PostgresBackend needs the {variable_name!r} Langflow variable "
                "(or env var of the same name) populated with a Postgres URL."
            )
            raise ValueError(msg)
        self._resolved_connection = value

    def _build_vector_store(self) -> VectorStore:
        # Validate config before attempting the optional import so
        # missing-collection / missing-URI surfaces as a clean
        # ``ValueError`` even on a host that hasn't installed the
        # langchain-postgres extra.
        collection_name = self._required("collection_name")
        connection = getattr(self, "_resolved_connection", None)
        if not connection:
            msg = "PostgresBackend.ensure_ready() must be awaited before _build_vector_store."
            raise RuntimeError(msg)

        try:
            from langchain_postgres import PGVector
        except ImportError as exc:
            msg = "PostgresBackend requires langchain-postgres. Install the 'postgres' extras or add the package."
            raise RuntimeError(msg) from exc

        return PGVector(
            embeddings=self.embedding_function,
            collection_name=collection_name,
            connection=connection,
            use_jsonb=True,
        )

    async def count(self) -> int:
        await self.ensure_ready()
        store = self.vector_store
        session_maker = getattr(store, "_session_maker", None) or getattr(store, "session_maker", None)
        if session_maker is None:
            return 0

        def _run() -> int:
            try:
                with session_maker() as session:
                    result = session.execute(_select_count_query(store))
                    row = result.first()
                    return int(row[0]) if row else 0
            except Exception as exc:  # noqa: BLE001
                logger.debug("Postgres count query failed: %s", exc)
                return 0

        return await asyncio.to_thread(_run)

    async def iter_documents(
        self,
        *,
        batch_size: int = 5000,
        include_embeddings: bool = False,
    ) -> AsyncIterator[list[IngestedDocument]]:
        await self.ensure_ready()
        store = self.vector_store
        session_maker = getattr(store, "_session_maker", None) or getattr(store, "session_maker", None)
        if session_maker is None:
            return

        # SQLAlchemy ``Session`` and psycopg ``Cursor`` objects are
        # NOT safe to share across threads — even sequential access
        # from different threads breaks the DB-API connection state.
        # ``asyncio.to_thread`` cannot pin subsequent calls to the
        # same worker thread, so we run the entire session lifetime
        # (open → iterate → close) inside *one* ``to_thread`` call
        # and stream batches back to the async side via a thread-
        # safe ``queue.Queue``.
        #
        # ``maxsize=2`` gives natural backpressure: the worker
        # blocks on ``queue.put`` once two batches are buffered,
        # matching what the caller is ready to consume.
        sentinel = object()
        batch_queue: sync_queue.Queue[Any] = sync_queue.Queue(maxsize=2)

        def _stream_batches() -> None:
            try:
                with session_maker() as session:
                    query = _select_rows_query(store, include_embeddings=include_embeddings)
                    result = session.execute(query)
                    while True:
                        rows = result.fetchmany(batch_size)
                        if not rows:
                            break
                        batch: list[IngestedDocument] = []
                        for row in rows:
                            content = row[0] or ""
                            metadata = row[1] or {}
                            embedding: list[float] | None = None
                            if include_embeddings and len(row) >= _ROWS_WITH_EMBEDDING_COLS:
                                raw_vec = row[2]
                                if raw_vec is not None:
                                    embedding = list(raw_vec)
                            batch.append(
                                IngestedDocument(
                                    content=str(content),
                                    metadata=dict(metadata) if isinstance(metadata, dict) else {},
                                    embedding=embedding,
                                )
                            )
                        if batch:
                            batch_queue.put(batch)
            except Exception as exc:  # noqa: BLE001
                batch_queue.put(exc)
            finally:
                batch_queue.put(sentinel)

        worker = asyncio.create_task(asyncio.to_thread(_stream_batches))
        sentinel_seen = False
        try:
            while True:
                item = await asyncio.to_thread(batch_queue.get)
                if item is sentinel:
                    sentinel_seen = True
                    break
                if isinstance(item, Exception):
                    logger.debug("Postgres iter_documents worker failed: %s", item)
                    sentinel_seen = True
                    # Worker has already queued the sentinel before
                    # re-raising — drain it so ``worker`` terminates.
                    await asyncio.to_thread(batch_queue.get)
                    break
                yield item
        finally:
            # If the caller abandoned iteration before the sentinel,
            # the worker may be blocked in ``queue.put``. Keep
            # draining until the sentinel arrives so it can exit.
            if not sentinel_seen:
                while True:
                    drained = await asyncio.to_thread(batch_queue.get)
                    if drained is sentinel:
                        break
            await worker

    async def storage_size_bytes(self) -> int:
        return 0

    async def teardown(self) -> None:
        store = getattr(self, "_vector_store", None)
        if store is not None:
            engine = getattr(store, "_engine", None) or getattr(store, "engine", None)
            if engine is not None and hasattr(engine, "dispose"):
                try:
                    await asyncio.to_thread(engine.dispose)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("PGVector engine.dispose failed: %s", exc)
        self._vector_store = None

    async def delete_collection(self) -> None:
        store = self.vector_store
        if hasattr(store, "delete_collection"):
            try:
                await asyncio.to_thread(store.delete_collection)
            except Exception as exc:  # noqa: BLE001
                logger.debug("PGVector delete_collection failed: %s", exc)


def _select_count_query(store: Any):
    """Build a COUNT(*) on the embedding table scoped to this collection."""
    from sqlalchemy import func, select

    embedding_model = _embedding_store_model(store)
    collection_id = _collection_id(store)
    return select(func.count()).select_from(embedding_model).where(embedding_model.collection_id == collection_id)


def _select_rows_query(store: Any, *, include_embeddings: bool):
    from sqlalchemy import select

    embedding_model = _embedding_store_model(store)
    collection_id = _collection_id(store)
    columns = [embedding_model.document, embedding_model.cmetadata]
    if include_embeddings:
        columns.append(embedding_model.embedding)
    return select(*columns).where(embedding_model.collection_id == collection_id)


def _embedding_store_model(store: Any):
    """Resolve the langchain_postgres EmbeddingStore model class."""
    for attr in ("EmbeddingStore", "_embedding_store", "embedding_store"):
        model = getattr(store, attr, None)
        if model is not None:
            return model
    msg = "langchain_postgres.PGVector does not expose an EmbeddingStore model"
    raise RuntimeError(msg)


def _collection_id(store: Any) -> Any:
    """Resolve the collection row id the store owns."""
    for attr in ("collection", "_collection"):
        collection = getattr(store, attr, None)
        if collection is None:
            continue
        for id_attr in ("uuid", "id"):
            value = getattr(collection, id_attr, None)
            if value is not None:
                return value
    msg = "langchain_postgres.PGVector does not expose a collection row"
    raise RuntimeError(msg)
