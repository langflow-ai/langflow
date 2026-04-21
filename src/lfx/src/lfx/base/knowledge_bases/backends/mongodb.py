"""MongoDB Atlas Vector Search backend.

Wraps ``langchain_mongodb.MongoDBAtlasVectorSearch``. The connection
URI + auth tokens come from Langflow variables (same pattern as S3
and the OAuth connectors) so the ``backend_config`` dict is safe to
round-trip through the UI — it carries variable *names*, never raw
secrets.

``backend_config`` shape::

    {
        "connection_uri_variable": "MONGODB_ATLAS_URI",
        "database": "my_db",
        "collection": "my_collection",
        "index_name": "vector_index",
        "text_key": "text",           # optional, default "text"
        "embedding_key": "embedding", # optional, default "embedding"
    }

``langchain_mongodb`` is optional. The backend imports it lazily so
Langflow installs without MongoDB-specific deps keep working; a
``MissingOptionalDependencyError`` surfaces the moment someone
selects this backend without installing the extra.
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

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langchain_core.vectorstores import VectorStore


DEFAULT_CONNECTION_URI_VARIABLE = "MONGODB_ATLAS_URI"
DEFAULT_TEXT_KEY = "text"
DEFAULT_EMBEDDING_KEY = "embedding"
DEFAULT_INDEX_NAME = "vector_index"


class MongoDBBackend(BaseVectorStoreBackend):
    """MongoDB Atlas Vector Search as a Langflow KB backend."""

    backend_type = BackendType.MONGODB

    def _required(self, key: str) -> str:
        value = self.backend_config.get(key)
        if not value:
            msg = f"MongoDBBackend requires '{key}' in backend_config."
            raise ValueError(msg)
        return str(value)

    async def _resolve_secrets(self) -> None:
        """Resolve the Atlas URI via Langflow's variable_service.

        Reads the variable name from ``backend_config`` (defaulting to
        ``MONGODB_ATLAS_URI``) and looks it up for ``self.user_id``.
        Falls back to a same-named environment variable when no UI
        variable is configured — keeps single-user / desktop setups
        working without forcing a browser roundtrip.
        """
        variable_name = self.backend_config.get("connection_uri_variable") or DEFAULT_CONNECTION_URI_VARIABLE
        value = await self.resolve_secret(variable_name)
        if not value:
            msg = (
                f"MongoDBBackend needs the {variable_name!r} Langflow variable "
                "(or env var of the same name) populated with the Atlas URI."
            )
            raise ValueError(msg)
        self._resolved_uri = value

    def _build_vector_store(self) -> VectorStore:
        # Validate config before touching optional deps so missing
        # fields surface as a clean ``ValueError`` regardless of
        # whether the langchain-mongodb extras are installed.
        database = self._required("database")
        collection_name = self._required("collection")
        uri = getattr(self, "_resolved_uri", None)
        if not uri:
            msg = "MongoDBBackend.ensure_ready() must be awaited before _build_vector_store."
            raise RuntimeError(msg)
        index_name = self.backend_config.get("index_name") or DEFAULT_INDEX_NAME
        text_key = self.backend_config.get("text_key") or DEFAULT_TEXT_KEY
        embedding_key = self.backend_config.get("embedding_key") or DEFAULT_EMBEDDING_KEY

        try:
            from langchain_mongodb import MongoDBAtlasVectorSearch
            from pymongo import MongoClient
        except ImportError as exc:
            msg = (
                "MongoDBBackend requires langchain-mongodb and pymongo. "
                "Install the 'mongodb' extras or add those packages."
            )
            raise RuntimeError(msg) from exc

        client = MongoClient(uri)
        collection = client[database][collection_name]
        # Stash so ``teardown`` can close the client cleanly.
        self._mongo_client = client
        return MongoDBAtlasVectorSearch(
            collection=collection,
            embedding=self.embedding_function,
            index_name=index_name,
            text_key=text_key,
            embedding_key=embedding_key,
        )

    async def count(self) -> int:
        # MongoDB collections expose ``estimated_document_count`` for
        # cheap counts; fall back to ``count_documents`` if the driver
        # doesn't surface it.
        await self.ensure_ready()
        client = getattr(self, "_mongo_client", None)
        if client is None:
            # Force a build so the collection is accessible.
            _ = self.vector_store
            client = self._mongo_client
        try:
            collection = client[self._required("database")][self._required("collection")]
            return int(await asyncio.to_thread(collection.estimated_document_count))
        except Exception as exc:  # noqa: BLE001
            logger.debug("MongoDB count() failed for %s: %s", self.kb_name, exc)
            return 0

    async def iter_documents(
        self,
        *,
        batch_size: int = 5000,
        include_embeddings: bool = False,
    ) -> AsyncIterator[list[IngestedDocument]]:
        """Paginate the collection via MongoDB's cursor."""
        await self.ensure_ready()
        client = getattr(self, "_mongo_client", None)
        if client is None:
            _ = self.vector_store
            client = self._mongo_client

        collection = client[self._required("database")][self._required("collection")]
        text_key = self.backend_config.get("text_key") or DEFAULT_TEXT_KEY
        embedding_key = self.backend_config.get("embedding_key") or DEFAULT_EMBEDDING_KEY

        projection: dict[str, Any] = {text_key: 1, "metadata": 1, "source_metadata": 1}
        if include_embeddings:
            projection[embedding_key] = 1

        # pymongo cursors are NOT thread-safe (client pools are, but
        # the cursor state is not). ``asyncio.to_thread`` can schedule
        # successive calls on different workers, so we run the entire
        # cursor lifetime (open → iterate → close) on *one* worker
        # thread and stream batches back to the async side via a
        # thread-safe queue. ``maxsize=2`` gives natural backpressure.
        sentinel = object()
        batch_queue: sync_queue.Queue[Any] = sync_queue.Queue(maxsize=2)

        def _stream_batches() -> None:
            cursor = None
            try:
                cursor = collection.find({}, projection=projection).batch_size(batch_size)
                buf: list[IngestedDocument] = []
                for raw in cursor:
                    content = raw.get(text_key) or ""
                    metadata = raw.get("metadata") or {
                        k: v for k, v in raw.items() if k not in {text_key, embedding_key, "_id", "metadata"}
                    }
                    embedding = raw.get(embedding_key) if include_embeddings else None
                    buf.append(
                        IngestedDocument(
                            content=str(content),
                            metadata=dict(metadata) if isinstance(metadata, dict) else {},
                            embedding=list(embedding) if embedding else None,
                        )
                    )
                    if len(buf) >= batch_size:
                        batch_queue.put(buf)
                        buf = []
                if buf:
                    batch_queue.put(buf)
            except Exception as exc:  # noqa: BLE001
                batch_queue.put(exc)
            finally:
                if cursor is not None:
                    try:
                        cursor.close()
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("MongoDB cursor close failed: %s", exc)
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
                    logger.debug("MongoDB iter_documents worker failed: %s", item)
                    sentinel_seen = True
                    await asyncio.to_thread(batch_queue.get)
                    break
                yield item
        finally:
            if not sentinel_seen:
                while True:
                    drained = await asyncio.to_thread(batch_queue.get)
                    if drained is sentinel:
                        break
            await worker

    async def storage_size_bytes(self) -> int:
        client = getattr(self, "_mongo_client", None)
        if client is None:
            return 0
        try:
            stats = await asyncio.to_thread(
                client[self._required("database")].command,
                {"collStats": self._required("collection")},
            )
            return int(stats.get("size") or 0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("MongoDB collStats failed for %s: %s", self.kb_name, exc)
            return 0

    async def teardown(self) -> None:
        client = getattr(self, "_mongo_client", None)
        if client is not None:
            try:
                await asyncio.to_thread(client.close)
            except Exception as exc:  # noqa: BLE001
                logger.debug("MongoClient.close failed: %s", exc)
        self._mongo_client = None
        self._vector_store = None

    async def delete_collection(self) -> None:
        """Drop the configured collection. Used by KB deletion."""
        client = getattr(self, "_mongo_client", None)
        if client is None:
            _ = self.vector_store
            client = self._mongo_client
        try:
            await asyncio.to_thread(
                client[self._required("database")].drop_collection,
                self._required("collection"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("MongoDB drop_collection failed: %s", exc)
