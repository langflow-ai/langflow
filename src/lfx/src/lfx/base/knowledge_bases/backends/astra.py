"""AstraDB vector-store backend.

Wraps ``langchain_astradb.AstraDBVectorStore``. Credentials are
variable-name references so ``backend_config`` round-trips safely to
the UI.

``backend_config`` shape::

    {
        "api_endpoint_variable": "ASTRA_DB_API_ENDPOINT",
        "token_variable": "ASTRA_DB_APPLICATION_TOKEN",
        "collection_name": "my_kb_collection",
        "namespace": "my_namespace",   # optional
    }
"""

from __future__ import annotations

import asyncio
import queue as sync_queue
import threading
from typing import TYPE_CHECKING, Any

from lfx.base.knowledge_bases.backends.base import (
    BackendType,
    BaseVectorStoreBackend,
    IngestedDocument,
    drain_queue_until_sentinel,
)
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langchain_core.vectorstores import VectorStore


DEFAULT_API_ENDPOINT_VARIABLE = "ASTRA_DB_API_ENDPOINT"
DEFAULT_TOKEN_VARIABLE = "ASTRA_DB_APPLICATION_TOKEN"  # noqa: S105 — variable name  # pragma: allowlist secret


class AstraBackend(BaseVectorStoreBackend):
    """AstraDB-backed Langflow Knowledge Base.

    Uses DataStax's serverless Cassandra + vector indexing. The
    serverless model means there's no local storage footprint — the
    ``kb_path`` stays relevant only for ``embedding_metadata.json``
    and similar sidecar files.
    """

    backend_type = BackendType.ASTRA

    def _required(self, key: str) -> str:
        value = self.backend_config.get(key)
        if not value:
            msg = f"AstraBackend requires '{key}' in backend_config."
            raise ValueError(msg)
        return str(value)

    async def _resolve_secrets(self) -> None:
        """Resolve the Astra API endpoint + app token via variable_service."""
        api_endpoint_var = self.backend_config.get("api_endpoint_variable") or DEFAULT_API_ENDPOINT_VARIABLE
        token_var = self.backend_config.get("token_variable") or DEFAULT_TOKEN_VARIABLE
        self._resolved_api_endpoint = await self.resolve_required_secret(api_endpoint_var)
        self._resolved_token = await self.resolve_required_secret(token_var)

    def _build_vector_store(self) -> VectorStore:
        # Config validation first so missing-field errors are
        # distinguishable from missing-dep errors.
        collection_name = self._required("collection_name")
        api_endpoint = getattr(self, "_resolved_api_endpoint", None)
        token = getattr(self, "_resolved_token", None)
        if not api_endpoint or not token:
            msg = "AstraBackend.ensure_ready() must be awaited before _build_vector_store."
            raise RuntimeError(msg)
        namespace = self.backend_config.get("namespace") or None

        try:
            from langchain_astradb import AstraDBVectorStore
        except ImportError as exc:
            msg = (
                "AstraBackend requires langchain-astradb. "
                "Install the 'astra' extras or add the package to your environment."
            )
            raise RuntimeError(msg) from exc

        return AstraDBVectorStore(
            embedding=self.embedding_function,
            collection_name=collection_name,
            api_endpoint=api_endpoint,
            token=token,
            namespace=namespace,
        )

    async def count(self) -> int:
        await self.ensure_ready()
        store = self.vector_store
        # langchain_astradb exposes the underlying collection on
        # ``.collection``; its ``count_documents`` is a cheap server-
        # side call.
        collection = getattr(store, "collection", None)
        if collection is None:
            return 0
        try:
            return int(await asyncio.to_thread(collection.count_documents))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Astra count_documents failed: %s", exc)
            return 0

    async def iter_documents(
        self,
        *,
        batch_size: int = 5000,
        include_embeddings: bool = False,
    ) -> AsyncIterator[list[IngestedDocument]]:
        await self.ensure_ready()
        store = self.vector_store
        collection = getattr(store, "collection", None)
        if collection is None:
            return

        projection: dict[str, int] = {"content": 1, "metadata": 1}
        if include_embeddings:
            projection["$vector"] = 1

        # astrapy cursors hold per-operation state tied to the HTTP
        # client that opened them. ``asyncio.to_thread`` can schedule
        # successive calls on different workers, so we run the entire
        # cursor lifetime (open → iterate → close) on *one* worker
        # thread and stream batches back via a thread-safe queue.
        # ``maxsize=2`` gives natural backpressure.
        #
        # ``cancel_event`` lets an early-exiting caller (e.g. the
        # retrieval path that only needs embeddings for the top-K
        # hits) tell the worker to stop iterating the cursor instead
        # of forcing a full collection scan.
        sentinel = object()
        batch_queue: sync_queue.Queue[Any] = sync_queue.Queue(maxsize=2)
        cancel_event = threading.Event()

        def _put_cancelable(item: Any) -> bool:
            """Enqueue ``item`` unless cancellation is observed first."""
            while not cancel_event.is_set():
                try:
                    batch_queue.put(item, timeout=0.05)
                except sync_queue.Full:
                    continue
                return True
            return False

        def _stream_batches() -> None:
            cursor = None
            try:
                cursor = collection.find({}, projection=projection)
                buf: list[IngestedDocument] = []
                for raw in cursor:
                    if cancel_event.is_set():
                        break
                    content = raw.get("content") or raw.get("text") or ""
                    metadata = raw.get("metadata") or {}
                    embedding = raw.get("$vector") if include_embeddings else None
                    buf.append(
                        IngestedDocument(
                            content=str(content),
                            metadata=dict(metadata) if isinstance(metadata, dict) else {},
                            embedding=list(embedding) if embedding else None,
                        )
                    )
                    if len(buf) >= batch_size:
                        if not _put_cancelable(buf):
                            buf = []
                            break
                        buf = []
                if buf and not cancel_event.is_set():
                    _put_cancelable(buf)
            except Exception as exc:  # noqa: BLE001
                if not cancel_event.is_set():
                    _put_cancelable(exc)
            finally:
                close = getattr(cursor, "close", None) if cursor is not None else None
                if callable(close):
                    try:
                        close()
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Astra cursor close failed: %s", exc)
                # Block until the sentinel lands. The async consumer's
                # finally drains the queue, guaranteeing progress here
                # even if the queue is full at cancel time.
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
                    logger.debug("Astra iter_documents worker failed: %s", item)
                    await asyncio.to_thread(batch_queue.get)
                    sentinel_seen = True
                    break
                yield item
        finally:
            cancel_event.set()
            if not sentinel_seen:
                await asyncio.to_thread(drain_queue_until_sentinel, batch_queue, sentinel)
            await worker

    async def storage_size_bytes(self) -> int:
        # Astra doesn't surface a simple bytes figure; approximate via
        # document count times a heuristic when needed. For now return 0.
        return 0

    async def teardown(self) -> None:
        # AstraDBVectorStore doesn't hold long-lived sockets (it uses
        # the Data API over HTTP), so there's nothing to close.
        self._vector_store = None

    async def delete_collection(self) -> None:
        store = self.vector_store
        try:
            # langchain_astradb exposes a clear() helper on recent versions.
            if hasattr(store, "clear"):
                await asyncio.to_thread(store.clear)
            elif hasattr(store, "delete_collection"):
                await asyncio.to_thread(store.delete_collection)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Astra clear/delete_collection failed: %s", exc)
