"""ChromaDB-backed ``VectorStoreBackend`` implementation.

This mirrors the behavior already present in ``kb_helpers`` — persistent
local storage, one collection per KB, a fresh client per instance to sidestep
SQLite "readonly" errors when ingestion and retrieval share a process.

Heavy lifting (SQLite lock recovery during KB *deletion*) stays in
``KBStorageHelper.delete_storage`` since it operates on paths, not on an open
backend handle.
"""

from __future__ import annotations

import contextlib
import gc
import uuid
from typing import TYPE_CHECKING, Any
from uuid import UUID

import chromadb
import chromadb.errors
from chromadb.api.shared_system_client import SharedSystemClient
from chromadb.config import Settings
from langchain_chroma import Chroma

from lfx.base.knowledge_bases.backends.base import (
    BackendType,
    BaseVectorStoreBackend,
    IngestedDocument,
)
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from langchain_core.embeddings import Embeddings
    from langchain_core.vectorstores import VectorStore


class ChromaBackend(BaseVectorStoreBackend):
    """Persistent Chroma collection scoped to a single KB directory."""

    backend_type = BackendType.CHROMA

    def __init__(
        self,
        kb_name: str,
        kb_path: Path,
        backend_config: dict[str, Any] | None = None,
        embedding_function: Embeddings | None = None,
        user_id: UUID | str | None = None,
    ) -> None:
        super().__init__(
            kb_name=kb_name,
            kb_path=kb_path,
            backend_config=backend_config,
            embedding_function=embedding_function,
            user_id=user_id,
        )
        self._client: chromadb.PersistentClient | None = None

    # ---- client plumbing -------------------------------------------------

    def _get_fresh_client(self) -> chromadb.PersistentClient:
        """Return a Chroma client with a unique session ID.

        Clearing the path's entry in Chroma's shared registry before building
        the client is what prevents "attempt to write a readonly database"
        when ingestion and retrieval touch the same directory in one process.
        """
        path_key = str(self.kb_path)
        # ``SharedSystemClient._identifier_to_system`` is internal but has
        # been stable across recent Chroma versions; guarded with try/except.
        try:
            if path_key in SharedSystemClient._identifier_to_system:  # noqa: SLF001
                del SharedSystemClient._identifier_to_system[path_key]  # noqa: SLF001
        except KeyError as exc:  # pragma: no cover — defensive
            logger.debug("Chroma registry clear failed for %s: %s", path_key, exc)

        return chromadb.PersistentClient(
            path=path_key,
            settings=Settings(
                is_persistent=True,
                persist_directory=path_key,
                chroma_otel_service_name=str(uuid.uuid4()),
            ),
        )

    def _build_vector_store(self) -> VectorStore:
        self._client = self._get_fresh_client()
        return Chroma(
            client=self._client,
            collection_name=self.kb_name,
            embedding_function=self.embedding_function,
        )

    # ---- overrides --------------------------------------------------------

    async def count(self) -> int:
        collection = self.vector_store._collection  # type: ignore[attr-defined]  # noqa: SLF001
        try:
            return collection.count()
        except chromadb.errors.ChromaError as exc:  # pragma: no cover — defensive
            logger.debug("Chroma count() failed for %s: %s", self.kb_name, exc)
            return 0

    async def iter_documents(
        self,
        *,
        batch_size: int = 5000,
        include_embeddings: bool = False,
    ) -> AsyncIterator[list[IngestedDocument]]:
        total = await self.count()
        if total <= 0:
            return

        collection = self.vector_store._collection  # type: ignore[attr-defined]  # noqa: SLF001
        include: list[str] = ["documents", "metadatas"]
        if include_embeddings:
            include.append("embeddings")

        for offset in range(0, total, batch_size):
            try:
                result = collection.get(include=include, limit=batch_size, offset=offset)
            except chromadb.errors.ChromaError as exc:
                logger.debug("Chroma get() failed at offset %d: %s", offset, exc)
                return

            documents = result.get("documents") or []
            metadatas = result.get("metadatas") or [{} for _ in documents]
            embeddings = result.get("embeddings") if include_embeddings else None

            batch: list[IngestedDocument] = []
            for idx, content in enumerate(documents):
                batch.append(
                    IngestedDocument(
                        content=content or "",
                        metadata=dict(metadatas[idx]) if idx < len(metadatas) else {},
                        embedding=(list(embeddings[idx]) if embeddings is not None and idx < len(embeddings) else None),
                    )
                )
            if batch:
                yield batch

    async def storage_size_bytes(self) -> int:
        if not self.kb_path.exists():
            return 0
        total = 0
        try:
            for file_path in self.kb_path.rglob("*"):
                if file_path.is_file():
                    total += file_path.stat().st_size
        except (OSError, PermissionError) as exc:  # pragma: no cover
            logger.debug("Size walk failed for %s: %s", self.kb_path, exc)
        return total

    async def teardown(self) -> None:
        """Release the Chroma client and clear the shared registry entry.

        Idempotent — safe to call from ``finally`` blocks even when
        ``_build_vector_store`` was never invoked.
        """
        path_key = str(self.kb_path)
        with contextlib.suppress(KeyError):
            # Intentionally silent: a missing key means someone else already
            # cleaned up this path.
            if path_key in SharedSystemClient._identifier_to_system:  # noqa: SLF001
                del SharedSystemClient._identifier_to_system[path_key]  # noqa: SLF001

        self._vector_store = None
        self._client = None
        gc.collect()

    # ---- Chroma-specific convenience --------------------------------------

    async def delete_collection(self) -> None:
        """Drop the collection entirely.

        Used by KB deletion, not by per-job cleanup. Catches Chroma errors
        because the collection may already be gone when a previous deletion
        partially succeeded.
        """
        store = self.vector_store
        with contextlib.suppress(chromadb.errors.ChromaError, OSError, ValueError):
            store.delete_collection()  # type: ignore[attr-defined]

    def raw_langchain_store(self) -> Chroma:
        """Expose the underlying LangChain Chroma instance.

        Only for call sites that still need Chroma-specific APIs during the
        Phase 0 transition (e.g. legacy code paths in ``kb_helpers`` that
        have not yet been ported).
        """
        return self.vector_store  # type: ignore[return-value]


def build_default_chroma_backend(
    kb_name: str,
    kb_path: Path,
    embedding_function: Embeddings | None = None,
) -> ChromaBackend:
    """Convenience factory used by shim code during the Phase 0 rollout.

    Keeps the existing ``kb_helpers`` call sites compact while the broader
    refactor lands.
    """
    return ChromaBackend(
        kb_name=kb_name,
        kb_path=kb_path,
        embedding_function=embedding_function,
    )
