"""ChromaDB-backed ``BaseVectorStoreBackend`` implementations.

Two independent classes cover the two Chroma deployment modes:

* ``ChromaLocalBackend`` — ``chromadb.PersistentClient`` backed by a local
  directory at ``kb_path``.  No credentials needed.
* ``ChromaCloudBackend`` — ``chromadb.CloudClient`` connecting to Chroma Cloud.
  Credentials (API key; optionally tenant / database) are resolved through
  Langflow's variable service or env vars.

``create_backend()`` in the registry dispatches to the right class based on
``backend_config["mode"]``; call sites never instantiate these directly.

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
    TestConnectionResult,
)
from lfx.base.vectorstores.chroma_security import chroma_langchain_collection_kwargs
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from chromadb.api import ClientAPI
    from langchain_core.embeddings import Embeddings
    from langchain_core.vectorstores import VectorStore


# ---------------------------------------------------------------------------
# Local backend
# ---------------------------------------------------------------------------


class ChromaLocalBackend(BaseVectorStoreBackend):
    """Chroma collection backed by a local ``PersistentClient``.

    Creates a fresh client per instance to sidestep SQLite "readonly" errors
    when ingestion and retrieval share a process.
    """

    backend_type = BackendType.CHROMA
    _is_cloud: bool = False

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
            **chroma_langchain_collection_kwargs(),
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
            if path_key in SharedSystemClient._identifier_to_system:  # noqa: SLF001
                del SharedSystemClient._identifier_to_system[path_key]  # noqa: SLF001

        self._vector_store = None
        self._client = None
        gc.collect()

    async def test_connection(self) -> TestConnectionResult:
        """Verify the persistent path is creatable and the client opens."""
        path_key = str(self.kb_path)
        try:
            self.kb_path.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as exc:
            return TestConnectionResult(
                ok=False,
                message=f"Knowledge base directory is not writable: {path_key}",
                details={"type": type(exc).__name__, "error": str(exc)},
            )

        client: chromadb.PersistentClient | None = None
        try:
            client = self._get_fresh_client()
            client.heartbeat()
        except Exception as exc:  # noqa: BLE001
            return TestConnectionResult(
                ok=False,
                message=str(exc) or type(exc).__name__,
                details={"type": type(exc).__name__},
            )
        finally:
            if client is not None:
                with contextlib.suppress(KeyError):
                    if path_key in SharedSystemClient._identifier_to_system:  # noqa: SLF001
                        del SharedSystemClient._identifier_to_system[path_key]  # noqa: SLF001
        return TestConnectionResult(
            ok=True,
            message="Chroma persistent client opened successfully.",
            details={"path": path_key},
        )

    async def delete_collection(self) -> None:
        """Drop the collection entirely (used by KB deletion)."""
        store = self.vector_store
        with contextlib.suppress(chromadb.errors.ChromaError, OSError, ValueError):
            store.delete_collection()  # type: ignore[attr-defined]

    def raw_langchain_store(self) -> Chroma:
        """Expose the underlying LangChain Chroma instance.

        Only for call sites that still need Chroma-specific APIs during the
        Phase 0 transition.
        """
        return self.vector_store  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Cloud backend
# ---------------------------------------------------------------------------


class ChromaCloudBackend(BaseVectorStoreBackend):
    """Chroma collection backed by a ``chromadb.CloudClient``.

    Credentials (API key, and optionally tenant / database) are resolved
    through Langflow's variable service (or env vars as a fallback) via the
    variable-name keys stored in ``backend_config``.
    """

    backend_type = BackendType.CHROMA
    _is_cloud: bool = True

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
        self._client: ClientAPI | None = None
        self._resolved_api_key: str | None = None
        self._resolved_tenant: str | None = None
        self._resolved_database: str | None = None

    # ---- credential resolution -------------------------------------------

    async def _resolve_secrets(self) -> None:
        cfg = self.backend_config
        # Only the API key is required. Tenant and database are optional —
        # chromadb infers them from the API key when absent.
        self._resolved_api_key = await self.resolve_required_secret(cfg.get("api_key_variable") or "CHROMA_API_KEY")
        self._resolved_tenant = await self.resolve_secret(cfg.get("tenant_variable") or "CHROMA_TENANT")
        self._resolved_database = await self.resolve_secret(cfg.get("database_variable") or "CHROMA_DATABASE")

    # ---- client plumbing -------------------------------------------------

    def _get_cloud_client(self) -> ClientAPI:
        cfg = self.backend_config
        kwargs: dict[str, Any] = {"api_key": self._resolved_api_key}
        if self._resolved_tenant:
            kwargs["tenant"] = self._resolved_tenant
        if self._resolved_database:
            kwargs["database"] = self._resolved_database
        if cfg.get("cloud_host"):
            kwargs["cloud_host"] = cfg["cloud_host"]
        if cfg.get("cloud_port"):
            kwargs["cloud_port"] = int(cfg["cloud_port"])
        # cloud_region stored for display; chromadb.CloudClient does not yet
        # accept a region parameter directly.
        return chromadb.CloudClient(**kwargs)

    def _build_vector_store(self) -> VectorStore:
        self._client = self._get_cloud_client()
        return Chroma(
            client=self._client,
            collection_name=self.kb_name,
            embedding_function=self.embedding_function,
            **chroma_langchain_collection_kwargs(),
        )

    # ---- overrides --------------------------------------------------------

    async def count(self) -> int:
        await self.ensure_ready()
        collection = self.vector_store._collection  # type: ignore[attr-defined]  # noqa: SLF001
        try:
            return collection.count()
        except chromadb.errors.ChromaError as exc:  # pragma: no cover — defensive
            logger.debug("Chroma Cloud count() failed for %s: %s", self.kb_name, exc)
            return 0

    async def iter_documents(
        self,
        *,
        batch_size: int = 300,
        include_embeddings: bool = False,
    ) -> AsyncIterator[list[IngestedDocument]]:
        await self.ensure_ready()
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
                logger.debug("Chroma Cloud get() failed at offset %d: %s", offset, exc)
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
        return 0

    async def teardown(self) -> None:
        """Release the cloud client reference."""
        self._vector_store = None
        self._client = None
        gc.collect()

    async def test_connection(self) -> TestConnectionResult:
        """Verify Chroma Cloud credentials and reachability via heartbeat."""
        try:
            await self._resolve_secrets()
            client = self._get_cloud_client()
            client.heartbeat()
        except Exception as exc:  # noqa: BLE001
            return TestConnectionResult(
                ok=False,
                message=str(exc) or type(exc).__name__,
                details={"type": type(exc).__name__},
            )
        cfg = self.backend_config
        return TestConnectionResult(
            ok=True,
            message="Chroma Cloud client connected successfully.",
            details={
                "tenant": self._resolved_tenant,
                "database": self._resolved_database,
                "host": cfg.get("cloud_host") or "api.trychroma.com",
                "region": cfg.get("cloud_region") or "us-east-1",
            },
        )

    async def delete_collection(self) -> None:
        """Delete the collection on Chroma Cloud.

        Errors propagate to the caller — the KB deletion route catches them
        via ``_delete_remote_backend_collection`` and surfaces a warning
        while still completing local storage and DB-row cleanup.
        """
        await self.ensure_ready()
        client = self._get_cloud_client()
        client.delete_collection(name=self.kb_name)

    def raw_langchain_store(self) -> Chroma:
        """Expose the underlying LangChain Chroma instance."""
        return self.vector_store  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Backward-compat alias + shim factory
# ---------------------------------------------------------------------------

# Alias retained so any import of ``ChromaBackend`` in shim code keeps working.
ChromaBackend = ChromaLocalBackend


def build_default_chroma_backend(
    kb_name: str,
    kb_path: Path,
    embedding_function: Embeddings | None = None,
) -> ChromaLocalBackend:
    """Convenience factory used by shim code during the Phase 0 rollout."""
    return ChromaLocalBackend(
        kb_name=kb_name,
        kb_path=kb_path,
        embedding_function=embedding_function,
    )
