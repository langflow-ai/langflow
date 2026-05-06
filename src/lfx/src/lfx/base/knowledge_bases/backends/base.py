"""Backend protocol and base class for Knowledge Base vector stores.

The backend abstraction is intentionally thin: LangChain's ``VectorStore``
already covers add / search / delete across every target backend (Chroma,
MongoDB Atlas, AstraDB, pgvector). We only need a uniform way to:

* build a backend given a KB name + backend-specific config + embedding fn,
* iterate stored documents (for metrics + visibility),
* count them,
* compute on-disk storage size (local backends) or cluster-side size
  approximation (hosted backends),
* tear down resources cleanly (file locks, network sessions, etc.),
* delete documents by filter for job rollback.

Backends MUST be safe to instantiate concurrently from async contexts. Each
call site is expected to obtain a fresh backend instance and tear it down via
``teardown()`` in a ``finally`` block.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.log.logger import logger

if TYPE_CHECKING:
    import queue as sync_queue
    from collections.abc import AsyncIterator
    from pathlib import Path

    from langchain_core.documents import Document
    from langchain_core.embeddings import Embeddings
    from langchain_core.vectorstores import VectorStore


def drain_queue_until_sentinel(queue: sync_queue.Queue, sentinel: Any) -> None:
    """Drain ``queue`` (blocking) until ``sentinel`` is observed.

    Shared helper for the single-worker ``iter_documents`` pattern used by
    Mongo / Astra / Postgres backends. Callers that set a ``threading.Event``
    to cancel the worker still need to drain so the worker's final
    ``put(sentinel)`` unblocks and the worker task can terminate.
    """
    while True:
        item = queue.get()
        if item is sentinel:
            return


class BackendType(str, Enum):
    """Registered vector-store backend identifiers.

    Keep values lowercase; they double as user-facing config strings.
    """

    CHROMA = "chroma"
    MONGODB = "mongodb"
    ASTRA = "astra"
    POSTGRES = "postgres"
    OPENSEARCH = "opensearch"


# Keys Langflow always writes into ``Document.metadata`` for every chunk.
# Kept here so every backend and helper agrees on the schema.
METADATA_KEY_SOURCE = "source"
METADATA_KEY_SOURCE_TYPE = "source_type"
METADATA_KEY_SOURCE_METADATA = "source_metadata"
METADATA_KEY_FILE_NAME = "file_name"
METADATA_KEY_CHUNK_INDEX = "chunk_index"
METADATA_KEY_TOTAL_CHUNKS = "total_chunks"
METADATA_KEY_INGESTED_AT = "ingested_at"
METADATA_KEY_JOB_ID = "job_id"


@dataclass(frozen=True)
class IngestedDocument:
    """Immutable view of a stored chunk returned by ``iter_documents``.

    Keeping this separate from ``langchain_core.documents.Document`` lets
    backends surface an embedding vector alongside the content without forcing
    every caller to reach into backend-specific internals.
    """

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None


@dataclass(frozen=True)
class TestConnectionResult:
    """Outcome of a backend ``test_connection`` call.

    ``ok`` is the only field the UI strictly needs. ``message`` is a short,
    user-facing summary safe to surface verbatim in a toast. ``details`` is an
    optional structured bag (e.g. ``{"type": "AuthenticationException"}``) for
    the frontend to render extra hints without parsing free-form text.
    """

    # Tell pytest not to try to collect this dataclass as a test class
    # just because its name starts with ``Test``.
    __test__ = False

    ok: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class BaseVectorStoreBackend(ABC):
    """Base class every KB vector-store backend inherits from.

    Wraps a LangChain ``VectorStore``: subclasses provide
    ``_build_vector_store`` and override ``storage_size_bytes`` /
    ``teardown`` / ``iter_documents`` where the LangChain primitives don't
    line up with what Langflow needs.

    Backends should be lightweight to construct; heavy resources (a Chroma
    persistent client, a MongoDB connection) are the backend's own concern
    and must be released in ``teardown``. Each call site obtains a fresh
    backend instance and tears it down via ``teardown()`` in a ``finally``
    block.
    """

    backend_type: BackendType

    def __init__(
        self,
        kb_name: str,
        kb_path: Path,
        backend_config: dict[str, Any] | None = None,
        embedding_function: Embeddings | None = None,
        user_id: UUID | str | None = None,
    ) -> None:
        self.kb_name = kb_name
        self.kb_path = kb_path
        self.backend_config = backend_config or {}
        self.embedding_function = embedding_function
        self.user_id = user_id
        self._vector_store: VectorStore | None = None

    # ---- credential resolution ------------------------------------------

    def _coerce_user_uuid(self) -> UUID | None:
        """Turn ``self.user_id`` into a ``UUID`` when possible."""
        if self.user_id is None:
            return None
        if isinstance(self.user_id, UUID):
            return self.user_id
        try:
            return UUID(str(self.user_id))
        except (ValueError, TypeError, AttributeError):
            return None

    async def resolve_secret(self, variable_name: str) -> str | None:
        """Look up ``variable_name`` through Langflow's variable service.

        Resolution order matches the connector ingestion sources
        (``connector_base.ConnectorIngestionSource.resolve_secret``):

        1. Langflow's ``variable_service`` scoped to ``self.user_id``.
        2. Process env var of the same name as a fallback for desktop /
           single-user deployments that skip the UI step.

        Returns ``None`` when neither source has a value; callers
        decide whether that's fatal. Never raises — ``_build_vector_store``
        is the right place for hard "credential missing" errors.
        """
        if not variable_name:
            return None

        user_uuid = self._coerce_user_uuid()
        if user_uuid is not None:
            try:
                from lfx.services.deps import get_variable_service, session_scope

                variable_service = get_variable_service()
                if variable_service is not None:
                    async with session_scope() as session:
                        value = await variable_service.get_variable(
                            user_id=user_uuid,
                            name=variable_name,
                            field="",
                            session=session,
                        )
                    if value:
                        # CREDENTIAL_TYPE variables are returned as SecretStr;
                        # str() on SecretStr yields "**********", not the secret.
                        try:
                            return value.get_secret_value()  # type: ignore[union-attr]
                        except AttributeError:
                            return str(value)
            except Exception as exc:  # noqa: BLE001 — fall through to env
                logger.debug("variable_service lookup for %s failed: %s", variable_name, exc)

        env_value = os.environ.get(variable_name)
        return env_value or None

    async def resolve_required_secret(self, variable_name: str) -> str:
        """Like ``resolve_secret`` but raises if no value is found."""
        value = await self.resolve_secret(variable_name)
        if not value:
            msg = (
                f"Required credential variable {variable_name!r} is not "
                "configured. Set it via Langflow's variable settings or as "
                "an environment variable on the server."
            )
            raise ValueError(msg)
        return value

    async def _resolve_secrets(self) -> None:
        """Hook for subclasses to resolve credential variables asynchronously.

        Called once, lazily, from ``ensure_ready`` before ``_build_vector_store``
        runs. Subclasses that need to translate ``backend_config`` variable
        names into live secrets override this and stash the values as
        instance attributes; ``_build_vector_store`` then reads those attrs
        synchronously.

        Default: no-op.
        """
        return

    async def ensure_ready(self) -> None:
        """Resolve async config exactly once before any vector-store access.

        Call sites (``kb_helpers``, ``retrieval.py``) await this after
        ``create_backend`` and before the first ``add_documents`` /
        ``similarity_search`` / ``iter_documents`` call. Idempotent so
        repeat calls are free.
        """
        if getattr(self, "_secrets_resolved", False):
            return
        await self._resolve_secrets()
        self._secrets_resolved = True

    # ---- subclass surface ------------------------------------------------

    @abstractmethod
    def _build_vector_store(self) -> VectorStore:
        """Build and return the concrete LangChain ``VectorStore`` instance."""

    # ---- public API ------------------------------------------------------

    @property
    def vector_store(self) -> VectorStore:
        """Lazy-built LangChain vector store."""
        if self._vector_store is None:
            self._vector_store = self._build_vector_store()
        return self._vector_store

    async def add_documents(self, docs: list[Document]) -> None:
        if not docs:
            return
        await self.ensure_ready()
        await self.vector_store.aadd_documents(docs)

    async def similarity_search(
        self,
        query: str,
        k: int,
        *,
        filter: dict[str, Any] | None = None,  # noqa: A002 — matches LangChain VectorStore API
        with_scores: bool = False,
    ) -> list[tuple[Document, float]]:
        await self.ensure_ready()
        if with_scores:
            return await self.vector_store.asimilarity_search_with_score(query=query, k=k, filter=filter)
        docs = await self.vector_store.asimilarity_search(query=query, k=k, filter=filter)
        return [(doc, 0.0) for doc in docs]

    async def delete_by(self, where: dict[str, Any]) -> None:
        await self.ensure_ready()
        await self.vector_store.adelete(where=where)

    async def count(self) -> int:
        # Default: iterate. Subclasses with a native count should override.
        await self.ensure_ready()
        total = 0
        async for batch in self.iter_documents(batch_size=5000):
            total += len(batch)
        return total

    async def iter_documents(  # pragma: no cover — overridden by subclasses
        self,
        *,
        batch_size: int = 5000,  # noqa: ARG002 — subclass override signature
        include_embeddings: bool = False,  # noqa: ARG002 — subclass override signature
    ) -> AsyncIterator[list[IngestedDocument]]:
        """Default implementation yields nothing; subclasses override."""
        if False:  # pragma: no cover — keeps this an async generator
            yield []

    async def storage_size_bytes(self) -> int:  # pragma: no cover
        """Default: unknown. Subclasses override where meaningful."""
        return 0

    async def delete_collection(self) -> None:  # pragma: no cover
        """Default: no-op. Concrete backends override when supported."""
        return

    async def teardown(self) -> None:  # pragma: no cover
        """Default: drop the LangChain reference and let GC handle the rest."""
        self._vector_store = None

    async def test_connection(self) -> TestConnectionResult:
        """Default: resolve secrets and ensure the LangChain store can build.

        For backends where ``_build_vector_store`` actually opens a network
        connection (e.g. clients that eagerly dial on construction) this is
        sufficient. Backends whose store builder is lazy should override and
        issue a backend-native ping (cluster info, SELECT 1, etc.) — the goal
        is to fail loudly at configure-time rather than waiting until the
        first ingestion call.
        """
        try:
            await self.ensure_ready()
            _ = self.vector_store
        except Exception as exc:  # noqa: BLE001 — converted to user-facing result
            return TestConnectionResult(
                ok=False,
                message=str(exc) or type(exc).__name__,
                details={"type": type(exc).__name__},
            )
        return TestConnectionResult(ok=True, message="Connection succeeded")
