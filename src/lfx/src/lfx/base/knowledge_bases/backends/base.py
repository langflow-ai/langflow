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

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID, uuid4

from lfx.log.logger import logger
from lfx.utils.env_var_security import safe_getenv

# Who controls a resolved secret's value. A Langflow variable is written by the
# tenant through the UI/API; a process env var can only be set by whoever runs the
# server. Destination policy for network backends turns on this distinction.
SecretSource = Literal["variable", "environment", "missing"]

if TYPE_CHECKING:
    import queue as sync_queue
    from collections.abc import AsyncIterator, Collection
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
    SQLITE = "sqlite"
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
# Content hash the Knowledge component stamps on every row it writes; used to
# skip rows that are already stored when duplicates are not allowed.
METADATA_KEY_CONTENT_ID = "_id"


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
    # The store's own id for the chunk. Carrying it lets a copy between stores
    # write each chunk under the same id, so re-running the copy upserts.
    id: str | None = None


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


class BackendConfigurationError(ValueError):
    """A permanent, operator-actionable backend misconfiguration.

    Raised for conditions that a retry of the same call can never fix: a missing
    database extension, an embedding-dimension mismatch between the stored
    collection and the current model, a missing privilege, etc. Ingestion's
    retry loop (``KBIngestionHelper.write_documents_to_backend``) re-raises these
    immediately instead of spending its backoff budget on a call that cannot
    succeed. Subclasses ``ValueError`` so existing ``except ValueError`` sites
    (and their tests) keep catching it.
    """


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

    @property
    def distance_metric(self) -> str | None:
        """Return the configured metric (cosine, l2, inner_product), or None if unknown."""
        return None

    def __init__(
        self,
        kb_name: str,
        kb_path: Path | None = None,
        backend_config: dict[str, Any] | None = None,
        embedding_function: Embeddings | None = None,
        user_id: UUID | str | None = None,
    ) -> None:
        # Legacy local Chroma uses kb_path. SQLite derives its own path from
        # trusted immutable storage context. Remote backends ignore it, so
        # their callers pass None rather than inventing a directory.
        """Capture backend configuration and the trusted storage and embedding context."""
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

        Thin wrapper over :meth:`resolve_secret_with_source` for the callers that
        only need the value. Returns ``None`` when neither source has a value;
        callers decide whether that's fatal. Never raises — ``_build_vector_store``
        is the right place for hard "credential missing" errors.
        """
        value, _source = await self.resolve_secret_with_source(variable_name)
        return value

    async def resolve_secret_with_source(self, variable_name: str) -> tuple[str | None, SecretSource]:
        """Resolve ``variable_name`` and report *who controls the value*.

        Resolution order matches the connector ingestion sources
        (``connector_base.ConnectorIngestionSource.resolve_secret``):

        1. Langflow's ``variable_service`` scoped to ``self.user_id``.
        2. Process env var of the same name as a fallback for desktop /
           single-user deployments that skip the UI step.

        The provenance matters for values that become a *network destination*.
        A Langflow variable is written by the tenant through the UI/API, so a URL
        from source ``"variable"`` is tenant-controlled. A process env var can only
        be set by whoever runs the server, so source ``"environment"`` is
        operator-controlled. ``destination_policy.enforce_kb_destination`` uses that
        distinction to decide whether a KB destination needs to be named in
        ``LANGFLOW_KB_ALLOWED_HOSTS``.

        Returns:
            ``(value, source)``, with source ``"missing"`` when neither lookup hit.
        """
        if not variable_name:
            return None, "missing"

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
                            return value.get_secret_value(), "variable"  # type: ignore[union-attr]
                        except AttributeError:
                            return str(value), "variable"
            except Exception as exc:  # noqa: BLE001 — fall through to env
                logger.debug("variable_service lookup for %s failed: %s", variable_name, exc)

        # safe_getenv denies reserved names (LANGFLOW_SECRET_KEY, DATABASE_URL, ...) so a
        # tenant-supplied KB secret name cannot exfiltrate the server's own secrets.
        env_value = safe_getenv(variable_name)
        if env_value:
            return env_value, "environment"
        return None, "missing"

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

    @property
    def store_location(self) -> tuple[Any, ...] | None:
        """Where this knowledge base's chunks live, once ``ensure_ready`` has run.

        Two backends of one class with equal locations read and write the same
        chunks, whatever their configs say. None means the backend does not say.
        """
        return None

    # ---- subclass surface ------------------------------------------------

    @abstractmethod
    def _build_vector_store(self) -> VectorStore:
        """Build and return the concrete LangChain ``VectorStore`` instance."""

    # ---- public API ------------------------------------------------------

    async def get_distance_metric(self) -> str | None:
        """Return the metric used by the store, resolving persisted settings if needed."""
        return self.distance_metric

    @property
    def vector_store(self) -> VectorStore:
        """Lazy-built LangChain vector store."""
        if self._vector_store is None:
            self._vector_store = self._build_vector_store()
        return self._vector_store

    async def add_documents(self, docs: list[Document]) -> None:
        """Write nonempty document batches through the initialized vector store."""
        if not docs:
            return
        await self.ensure_ready()
        await self.vector_store.aadd_documents(docs)

    async def add_embedded_documents(self, docs: list[IngestedDocument]) -> None:
        """Write chunks whose vectors are already computed, without re-embedding.

        This is how a knowledge base moves between stores: what one backend
        returns from ``iter_documents(include_embeddings=True)`` is written here
        as-is, so no embedding model or provider credentials are involved.

        Every document needs an ``embedding`` of the same width. A document with
        an ``id`` is written under that id, so writing the same batch twice
        upserts instead of duplicating; one without gets a fresh id.
        """
        if not docs:
            return
        missing = [i for i, doc in enumerate(docs) if doc.embedding is None or len(doc.embedding) == 0]
        if missing:
            msg = f"add_embedded_documents needs an embedding on every document; missing at positions {missing[:5]}"
            raise ValueError(msg)
        widths = {len(doc.embedding) for doc in docs}  # type: ignore[arg-type]
        if len(widths) > 1:
            msg = f"add_embedded_documents needs one embedding width per batch; got {sorted(widths)}"
            raise ValueError(msg)
        await self.ensure_ready()
        await self._write_embedded([doc.id or str(uuid4()) for doc in docs], docs)

    async def _write_embedded(self, ids: list[str], docs: list[IngestedDocument]) -> None:
        """Store ``docs`` under ``ids`` with their existing vectors. Backends override this.

        There is deliberately no fallback: a silent no-op here would read as a
        successful copy that lost every chunk.
        """
        msg = f"{type(self).__name__} does not support writing precomputed embeddings"
        raise NotImplementedError(msg)

    async def similarity_search(
        self,
        query: str,
        k: int,
        *,
        filter: dict[str, Any] | None = None,  # noqa: A002 — matches LangChain VectorStore API
        with_scores: bool = False,
    ) -> list[tuple[Document, float]]:
        """Search with metadata filters and optionally return provider distance scores."""
        await self.ensure_ready()
        if with_scores:
            return await self.vector_store.asimilarity_search_with_score(query=query, k=k, filter=filter)
        docs = await self.vector_store.asimilarity_search(query=query, k=k, filter=filter)
        return [(doc, 0.0) for doc in docs]

    def normalize_score(self, score: float) -> float:
        """Convert this backend's distance score to the public higher-is-better contract."""
        return -float(score)

    async def delete_by(self, where: dict[str, Any]) -> None:
        """Delete matching documents through the initialized vector store."""
        await self.ensure_ready()
        await self.vector_store.adelete(where=where)

    async def count(self) -> int:
        # Default: iterate. Subclasses with a native count should override.
        """Count documents by streaming batches when the backend has no native count."""
        await self.ensure_ready()
        total = 0
        async for batch in self.iter_documents(batch_size=5000):
            total += len(batch)
        return total

    async def read_only_count(self) -> int | None:
        """How many chunks the store holds, read without creating the store or anything in it.

        None when the store does not exist. The default is ``count``, for backends
        whose count only reads; a backend whose count can create storage overrides it.
        """
        return await self.count()

    async def iter_documents(  # pragma: no cover — overridden by subclasses
        self,
        *,
        batch_size: int = 5000,  # noqa: ARG002 — subclass override signature
        include_embeddings: bool = False,  # noqa: ARG002 — subclass override signature
    ) -> AsyncIterator[list[IngestedDocument]]:
        """Default implementation yields nothing; subclasses override."""
        if False:  # pragma: no cover — keeps this an async generator
            yield []

    async def existing_content_ids(self, content_ids: Collection[str]) -> set[str]:
        """Return the subset of ``content_ids`` already stored as a chunk's ``_id``.

        Ingestion calls this to skip rows it has already written. This default
        streams the whole collection; backends that can look the ids up directly
        override it so the cost follows the new rows, not the collection size.
        """
        wanted = {content_id for content_id in content_ids if content_id}
        found: set[str] = set()
        if not wanted:
            return found
        async for batch in self.iter_documents():
            for document in batch:
                content_id = document.metadata.get(METADATA_KEY_CONTENT_ID)
                if content_id in wanted:
                    found.add(content_id)
        return found

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
