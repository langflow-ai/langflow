"""ChromaDB-backed ``BaseVectorStoreBackend`` implementations.

Two independent classes cover the two Chroma deployment modes:

* ``ChromaLocalBackend`` — ``chromadb.PersistentClient`` backed by a local
  directory at ``kb_path``.  No credentials needed.
* ``ChromaCloudBackend`` — ``chromadb.CloudClient`` connecting to Chroma Cloud.
  Credentials (API key; optionally tenant / database) are resolved through
  Langflow's variable service or env vars. Users who resolve to the same tenant
  and database share one namespace, so the collection is owner-scoped (the same
  ``lf_<sha256[:24]>`` name pgvector gives the KB's table) rather than named
  after the KB, whose name is only unique per user. ``backend_config`` may set
  ``collection_name`` to use an existing collection instead; Alembic revision
  ``386662af02e9`` pins KBs created before owner scoping to their ``kb_name``
  collection that way, or records ``legacy_shared_collection`` when KBs of
  several owners already used that collection. Only a superuser may persist
  ``collection_name`` (see ``naming.ensure_storage_routing_allowed``).

``create_backend()`` in the registry dispatches to the right class based on
``backend_config["mode"]``; call sites never instantiate these directly.

Heavy lifting (SQLite lock recovery during KB *deletion*) stays in
``KBStorageHelper.delete_storage`` since it operates on paths, not on an open
backend handle.
"""

from __future__ import annotations

import asyncio
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
from lfx.base.knowledge_bases.backends.destination_policy import enforce_kb_destination
from lfx.base.knowledge_bases.backends.naming import resolve_storage_name
from lfx.base.vectorstores.chroma_security import chroma_langchain_collection_kwargs
from lfx.log.logger import logger
from lfx.utils.ssrf_protection import SSRFProtectionError, validate_connector_url_for_ssrf

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from chromadb.api import ClientAPI
    from langchain_core.embeddings import Embeddings
    from langchain_core.vectorstores import VectorStore


# ``backend_config`` keys for Chroma Cloud collection routing. The origin and
# shared markers are written by alembic revision ``386662af02e9``.
COLLECTION_NAME_KEY = "collection_name"
COLLECTION_NAME_ORIGIN_KEY = "collection_name_origin"
LEGACY_SHARED_COLLECTION_KEY = "legacy_shared_collection"


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
        kb_path: Path | None = None,
        backend_config: dict[str, Any] | None = None,
        embedding_function: Embeddings | None = None,
        user_id: UUID | str | None = None,
    ) -> None:
        # Local Chroma is the one backend that genuinely needs a directory, so it
        # is also the one that must refuse ``None``. Failing here — at
        # construction, naming the KB — beats a downstream ``str(None)`` that
        # would quietly persist the collection into a directory called "None".
        if kb_path is None:
            msg = (
                f"Local Chroma requires an on-disk path but none was resolved for knowledge base {kb_name!r}. "
                "This usually means the KB's backend was resolved as local Chroma on a deployment that "
                "does not provide local storage; configure a remote vector store for it instead."
            )
            raise ValueError(msg)
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
        kb_path: Path | None = None,
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
        await self._validate_cloud_target()

    async def _validate_cloud_target(self) -> None:
        """SSRF-validate the tenant-controlled ``cloud_host`` / ``cloud_port``.

        Both keys come straight from the request body's ``backend_config`` and
        land in ``chromadb.CloudClient``, which makes server-side connections
        whose outcome the test-connection route echoes back. Without validation
        a tenant can probe cloud-metadata (169.254.169.254), RFC1918, or loopback
        targets from the server's network position. Apply the same connector SSRF
        policy every other tenant-URL sink uses; operators reach legitimate
        internal hosts via ``LANGFLOW_SSRF_ALLOWED_HOSTS``. ``resolve_hostname``
        blocks, so the check runs off the event loop. An absent ``cloud_host``
        means the chromadb default (``api.trychroma.com``), a fixed public host
        with no tenant input, so neither gate has anything to judge.

        A custom host also has to clear ``enforce_kb_destination``: chromadb builds
        its own ``httpx`` client inside ``CloudClient`` and dials during
        construction, so the address this check validates cannot be pinned for the
        connection that follows. ``cloud_host`` is a testing-only knob upstream
        (chromadb marks it so), so requiring the operator to approve it in
        ``LANGFLOW_KB_ALLOWED_HOSTS`` leaves the ordinary Chroma Cloud path alone.
        """
        cfg = self.backend_config
        cloud_host = cfg.get("cloud_host")
        if not cloud_host:
            return
        host = str(cloud_host)
        port = cfg.get("cloud_port")
        # chromadb.CloudClient takes a bare host (https implied); keep an
        # explicit scheme when one was supplied, else construct an https URL so
        # the validator has a parseable target.
        target = host if "://" in host else f"https://{host}:{int(port) if port else 443}"
        # ``cloud_host`` always arrives in the request body, so it is tenant-supplied by
        # construction — there is no env-var provenance to consider here. chromadb builds its
        # own httpx client (and dials during construction), so the validated address cannot be
        # pinned; the operator has to have approved the host.
        enforce_kb_destination(target, source="request", description="the knowledge base's cloud_host")
        try:
            await asyncio.to_thread(validate_connector_url_for_ssrf, target)
        except SSRFProtectionError as exc:
            # Re-raised as SSRFProtectionError (a ValueError subclass, so existing config
            # paths still catch it): test_connection echoes type(exc).__name__ back to the
            # caller, and a blocked destination should not read as a missing credential.
            msg = f"Chroma Cloud host is not allowed: {exc}"
            raise SSRFProtectionError(msg) from exc

    # ---- client plumbing -------------------------------------------------

    def _get_cloud_client(self) -> ClientAPI:
        cfg = self.backend_config
        kwargs: dict[str, Any] = {"api_key": self._resolved_api_key}
        if self._resolved_tenant:
            kwargs["tenant"] = self._resolved_tenant
        if self._resolved_database:
            kwargs["database"] = self._resolved_database
        if cfg.get("cloud_host"):
            # The SSRF check on this host lives in ``_validate_cloud_target``, which
            # ``ensure_ready`` runs before anything can reach here. It used to be
            # repeated inline at this point too, which resolved DNS twice per client
            # and — because ``vector_store`` builds lazily from a sync property — ran a
            # blocking lookup on the event loop for every ingest and search.
            kwargs["cloud_host"] = cfg["cloud_host"]
        if cfg.get("cloud_port"):
            kwargs["cloud_port"] = int(cfg["cloud_port"])
        # cloud_region stored for display; chromadb.CloudClient does not yet
        # accept a region parameter directly.
        return chromadb.CloudClient(**kwargs)

    def _resolve_collection_name(self) -> str:
        """Resolve this KB's collection in the resolved tenant and database.

        Unlike local Chroma, which isolates each owner under its own directory,
        every user whose credentials resolve to the same tenant and database
        shares one collection namespace.
        """
        return resolve_storage_name(
            kb_name=self.kb_name,
            owner_id=self._coerce_user_uuid(),
            override=self.backend_config.get(COLLECTION_NAME_KEY),
            override_key=COLLECTION_NAME_KEY,
            backend="ChromaCloudBackend",
            storage="collection",
        )

    def _build_vector_store(self) -> VectorStore:
        collection_name = self._resolve_collection_name()
        shared_legacy_collection = self.backend_config.get(LEGACY_SHARED_COLLECTION_KEY)
        if shared_legacy_collection and collection_name != shared_legacy_collection:
            logger.warning(
                "Knowledge base %s no longer uses Chroma Cloud collection %s: another user's knowledge base used "
                "the same collection, or the name is reserved for owner-scoped collections. Its earlier chunks "
                "were left in %s, and it now uses its own collection %s. Re-ingest its sources to restore them.",
                self.kb_name,
                shared_legacy_collection,
                shared_legacy_collection,
                collection_name,
            )
        self._client = self._get_cloud_client()
        return Chroma(
            client=self._client,
            collection_name=collection_name,
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
            # Sync construction (SSRF validation resolves DNS, CloudClient opens a
            # connection) called from async: keep it off the event loop.
            client = await asyncio.to_thread(self._get_cloud_client)
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
        collection_name = self._resolve_collection_name()
        # Sync construction (SSRF validation resolves DNS, CloudClient opens a
        # connection) called from async: keep it off the event loop.
        client = await asyncio.to_thread(self._get_cloud_client)
        client.delete_collection(name=collection_name)

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
