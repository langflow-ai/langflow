"""Postgres (pgvector) vector-store backend.

The backend is configured by one deployment-level
``PGVECTOR_CONNECTION_STRING`` environment variable. Each Knowledge Base or
Memory Base maps to a stable, owner-qualified collection so users may safely use
the same display name.

Storage layout
--------------
Every collection gets its **own** physical table, named after its
owner-qualified ``collection_name`` (``lf_<sha256[:24]>``). The embedding column
is typed to the collection's embedding dimension (``vector(N)``) so pgvector can
build an HNSW index on it — a dimensionless ``vector`` column cannot be indexed
and forces a sequential scan on every search. Because each table carries its own
dimension, different KBs may use different embedding models side by side.

The small async adapter below deliberately uses SQLAlchemy + ``pgvector``
directly. This keeps the published ``pgvector`` extra satisfiable while
preserving Langflow's security floor on the Python pgvector client; released
``langchain-postgres`` versions still require ``pgvector<0.4``.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import TYPE_CHECKING, Any

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

from lfx.base.knowledge_bases.backends.base import (
    BackendType,
    BaseVectorStoreBackend,
    IngestedDocument,
    TestConnectionResult,
)
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from sqlalchemy.ext.asyncio import AsyncConnection


# Single env var that configures pgVector for the whole deployment.
DEFAULT_CONNECTION_STRING_VARIABLE = "PGVECTOR_CONNECTION_STRING"

# Process-wide advisory-lock key serializing per-collection DDL (table + index
# creation) so concurrent ingests don't race the bootstrap.
_ADVISORY_LOCK_KEY = 1573678846307946496

# Collection tables are always ``lf_`` + 24 lowercase hex chars derived from a
# sha256 of the owner id + KB name (see ``collection_name``). The value is never
# user input, but every interpolation of it into SQL is still guarded against
# this exact shape so the S608 posture holds even if the derivation changes.
_COLLECTION_NAME_RE = re.compile(r"^lf_[0-9a-f]{24}$")

# pgvector can build an HNSW index on a ``vector`` column only up to this many
# dimensions. Larger models (e.g. 3072-dim embeddings) still store and search
# correctly — they just fall back to an exact (sequential) scan until halfvec
# indexing is wired up. See ``_ensure_embedding_table``.
_HNSW_MAX_DIM = 2000

# Static, table-name-free SQL (name is a bound param, missing table -> 0).
_STORAGE_SIZE_SQL = "SELECT COALESCE(pg_total_relation_size(to_regclass(:name)), 0)"

# Separation of duties: the ``vector`` extension is privileged DDL on the
# database catalog, so *the operator* provisions it — Langflow only reads and
# writes. Every site that detects the extension's absence (``test_connection``,
# first-ingest table setup, and — once wired — the deployment pre-flight probe)
# surfaces this one message so the resolution is always the same, clear step.
MISSING_EXTENSION_MESSAGE = (
    "The pgvector 'vector' extension is not installed on this database. Ask your "
    "database operator to enable it by running `CREATE EXTENSION vector;` as a "
    "superuser. Langflow does not install database extensions — it only reads from "
    "and writes to the database."
)
# ``details.type`` tag the frontend keys off to render extension-specific hints.
MISSING_EXTENSION_DETAILS_TYPE = "MissingExtension"


def _validate_table_name(name: str) -> str:
    """Return ``name`` iff it matches the fixed collection-table shape.

    Guards every place a collection table name is interpolated into SQL text.
    """
    if not _COLLECTION_NAME_RE.match(name):
        msg = f"Refusing to build SQL for an unexpected collection table name: {name!r}."
        raise ValueError(msg)
    return name


def _count_sql(table: str) -> str:
    return f"SELECT count(*) FROM {_validate_table_name(table)}"  # noqa: S608 — table name validated above


def _delete_by_sql(table: str) -> str:
    return (
        f"DELETE FROM {_validate_table_name(table)} "  # noqa: S608 — table name validated; :where is bound
        "WHERE cmetadata @> CAST(:where AS jsonb)"
    )


def _drop_table_sql(table: str) -> str:
    return f'DROP TABLE IF EXISTS "{_validate_table_name(table)}"'


def _iter_documents_sql(table: str, *, include_embeddings: bool) -> str:
    columns = "document, cmetadata" + (", embedding" if include_embeddings else "")
    return f"SELECT {columns} FROM {_validate_table_name(table)}"  # noqa: S608 — table name validated above


def _parse_vector_dim(type_str: str | None) -> int | None:
    """Extract N from a ``vector(N)`` Postgres type string."""
    match = re.search(r"vector\((\d+)\)", type_str or "")
    return int(match.group(1)) if match else None


def _normalize_driver(url: str) -> str:
    """Force the psycopg3 driver the sync store + the async sidecar engine need."""
    if url.startswith("postgresql+psycopg://"):
        return url
    for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.split("://", 1)[1]
    return url


def read_connection_string_from_env() -> str | None:
    """Read the pgVector connection string from the server environment.

    This is the one intentional direct read of this protected server credential.
    The name is fixed in code and can never be supplied by a tenant.
    """
    import os

    return os.getenv(DEFAULT_CONNECTION_STRING_VARIABLE) or None


def postgres_env_configured() -> bool:
    """Return True when pgVector is provisioned via env (the auto-default trigger)."""
    return bool(read_connection_string_from_env())


def resolve_default_kb_backend() -> str:
    """Return the backend for a new KB when the client omits a selection."""
    return BackendType.POSTGRES.value if postgres_env_configured() else BackendType.CHROMA.value


def _coerce_embedding(raw: Any) -> list[float] | None:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        return [float(v) for v in raw]
    try:  # pgvector often round-trips as "[0.1,0.2,...]"
        return [float(v) for v in json.loads(str(raw))]
    except (ValueError, TypeError):
        return None


class _PostgresVectorStore(VectorStore):
    """Async LangChain VectorStore facade over ``PostgresBackend``."""

    def __init__(self, backend: PostgresBackend) -> None:
        self._backend = backend

    @property
    def embeddings(self):
        return self._backend.embedding_function

    @classmethod
    def from_texts(cls, *args, **kwargs):
        msg = "PostgresVectorStore must be constructed through PostgresBackend."
        raise NotImplementedError(msg)

    def similarity_search(self, *args, **kwargs):
        msg = "Use the async PostgresVectorStore search methods."
        raise NotImplementedError(msg)

    async def aadd_documents(self, documents: list[Document], **kwargs: Any) -> list[str]:
        return await self._backend._add_documents(documents, ids=kwargs.get("ids"))  # noqa: SLF001

    async def asimilarity_search(
        self,
        query: str,
        k: int = 4,
        *,
        filter: dict[str, Any] | None = None,  # noqa: A002
        **kwargs: Any,  # noqa: ARG002
    ) -> list[Document]:
        results = await self._backend._similarity_search(query, k=k, filter=filter)  # noqa: SLF001
        return [document for document, _score in results]

    async def asimilarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        *,
        filter: dict[str, Any] | None = None,  # noqa: A002
        **kwargs: Any,  # noqa: ARG002
    ) -> list[tuple[Document, float]]:
        return await self._backend._similarity_search(query, k=k, filter=filter)  # noqa: SLF001


class PostgresBackend(BaseVectorStoreBackend):
    """Postgres + pgvector as a Langflow KB backend (environment-driven)."""

    backend_type = BackendType.POSTGRES

    # ---- config / secret resolution -------------------------------------

    async def _resolve_secrets(self) -> None:
        # Never honor a backend_config-provided environment-variable name here:
        # backend_config is tenant-controlled, while this credential belongs to
        # the deployment.
        connection_string = read_connection_string_from_env()
        if not connection_string:
            msg = (
                f"PostgresBackend needs the {DEFAULT_CONNECTION_STRING_VARIABLE!r} environment variable populated "
                "with a "
                "Postgres connection string, e.g. "
                "'postgresql+psycopg://user:pass@host:5432/dbname'."  # pragma: allowlist secret
            )
            raise ValueError(msg)
        self._resolved_connection_string = _normalize_driver(connection_string)

    @property
    def collection_name(self) -> str:
        """Return a stable, non-identifying collection name scoped to the owner."""
        owner_id = self._coerce_user_uuid()
        if owner_id is None:
            msg = "PostgresBackend requires a valid user_id to isolate its collection."
            raise ValueError(msg)
        owner = str(owner_id)
        payload = f"{len(owner)}:{owner}{len(self.kb_name)}:{self.kb_name}"
        return f"lf_{hashlib.sha256(payload.encode()).hexdigest()[:24]}"

    @property
    def table_name(self) -> str:
        """Physical embedding table for this collection (validated for SQL use)."""
        return _validate_table_name(self.collection_name)

    def _ensure_async_engine(self):
        """Lazily build the sidecar async engine used for count/scan/delete/ping."""
        engine = getattr(self, "_pg_engine", None)
        if engine is not None:
            return engine
        connection_string = getattr(self, "_resolved_connection_string", None)
        if not connection_string:
            msg = "PostgresBackend.ensure_ready() must be awaited before touching the database."
            raise RuntimeError(msg)
        try:
            from sqlalchemy.ext.asyncio import create_async_engine
        except ImportError as exc:  # pragma: no cover
            msg = "PostgresBackend requires SQLAlchemy async support (install the pgvector extra)."
            raise RuntimeError(msg) from exc
        engine = create_async_engine(connection_string, pool_pre_ping=True)
        self._pg_engine = engine
        return engine

    def _require_pgvector(self) -> None:
        """Raise a friendly RuntimeError when the optional pgvector extra is absent."""
        try:
            from pgvector.sqlalchemy import Vector  # noqa: F401
        except (ImportError, RuntimeError) as exc:
            msg = (
                "PostgresBackend requires the 'pgvector' package. "
                "Install the pgvector extra, e.g. pip install 'langflow[pgvector]'."
            )
            raise RuntimeError(msg) from exc

    def _embedding_table(self, dim: int | None = None):
        """Build the per-collection embedding table definition.

        ``dim`` types the vector column for DDL; read/write query construction
        does not depend on it, so callers that only reference the column may
        leave it ``None``.
        """
        self._require_pgvector()
        from pgvector.sqlalchemy import Vector
        from sqlalchemy import Column, MetaData, String, Table
        from sqlalchemy.dialects.postgresql import JSONB

        metadata = MetaData()
        return Table(
            self.table_name,
            metadata,
            Column("id", String, primary_key=True),
            Column("embedding", Vector(dim) if dim else Vector()),
            Column("document", String, nullable=True),
            Column("cmetadata", JSONB, nullable=True),
        )

    async def _existing_embedding_dim(self, conn: AsyncConnection) -> int | None:
        """Return the dimension of an existing collection table, or None if absent."""
        from sqlalchemy import text

        type_str = await conn.scalar(
            text(
                "SELECT format_type(a.atttypid, a.atttypmod) "
                "FROM pg_attribute a JOIN pg_class c ON a.attrelid = c.oid "
                "WHERE c.relname = :name AND a.attname = 'embedding' "
                "AND a.attnum > 0 AND NOT a.attisdropped"
            ),
            {"name": self.table_name},
        )
        return _parse_vector_dim(type_str)

    async def _ensure_embedding_table(self, dim: int) -> None:
        """Create this collection's typed, indexed table (idempotent).

        Runs under a process-wide advisory lock so concurrent first-ingests of
        the same (or different) collections don't race the DDL. The HNSW and GIN
        indexes are built at creation time while the table is empty, which is
        cheap and avoids ``CREATE INDEX CONCURRENTLY``'s no-transaction rule.

        The ``vector`` extension is **not** created here: provisioning it is the
        database operator's responsibility (see ``MISSING_EXTENSION_MESSAGE``).
        Its absence is checked up front and surfaced with a clear, actionable
        message rather than failing obscurely on the ``vector(N)`` column type.
        """
        dim = int(dim)
        if dim <= 0:
            msg = f"Embedding dimension must be a positive integer, got {dim!r}."
            raise ValueError(msg)
        table = self.table_name
        self._require_pgvector()
        from sqlalchemy import text

        engine = self._ensure_async_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK_KEY})
            # Operator owns the extension; Langflow verifies, never creates it.
            if not await self._vector_extension_installed(conn):
                raise ValueError(MISSING_EXTENSION_MESSAGE)
            await conn.execute(
                text(
                    f'CREATE TABLE IF NOT EXISTS "{table}" ('
                    "id VARCHAR PRIMARY KEY, "
                    f"embedding vector({dim}), "
                    "document VARCHAR, "
                    "cmetadata JSONB)"
                )
            )
            # ``CREATE TABLE IF NOT EXISTS`` never alters an existing table, so a
            # model whose dimension differs from the one this KB was created with
            # would fail obscurely on INSERT. Surface it clearly instead.
            existing_dim = await self._existing_embedding_dim(conn)
            if existing_dim is not None and existing_dim != dim:
                msg = (
                    f"Knowledge base '{self.kb_name}' was created with {existing_dim}-dimensional embeddings, "
                    f"but the current embedding model produces {dim}. Recreate the knowledge base or restore the "
                    "original embedding model."
                )
                raise ValueError(msg)
            await conn.execute(
                text(
                    f'CREATE INDEX IF NOT EXISTS "{table}_cmeta_gin" ON "{table}" USING gin (cmetadata jsonb_path_ops)'
                )
            )
            if dim <= _HNSW_MAX_DIM:
                await conn.execute(
                    text(
                        f'CREATE INDEX IF NOT EXISTS "{table}_hnsw" ON "{table}" '
                        "USING hnsw (embedding vector_cosine_ops)"
                    )
                )
            else:
                await logger.awarning(
                    "pgvector cannot HNSW-index %d-dimensional embeddings (max %d) for %s; "
                    "similarity search will use an exact scan.",
                    dim,
                    _HNSW_MAX_DIM,
                    self.kb_name,
                )

    async def _table_exists(self, conn: AsyncConnection) -> bool:
        from sqlalchemy import text

        return (await conn.scalar(text("SELECT to_regclass(:name)"), {"name": self.table_name})) is not None

    async def _vector_extension_installed(self, conn: AsyncConnection) -> bool:
        """Return True iff the pgvector ``vector`` extension exists on this database."""
        from sqlalchemy import text

        return bool(await conn.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")))

    # ---- the one required method ----------------------------------------

    def _build_vector_store(self) -> VectorStore:
        return _PostgresVectorStore(self)

    async def _add_documents(self, documents: list[Document], *, ids: Sequence[str] | None = None) -> list[str]:
        await self.ensure_ready()
        if self.embedding_function is None:
            msg = "PostgresBackend requires an embedding function to add documents."
            raise ValueError(msg)
        vectors = await self.embedding_function.aembed_documents([document.page_content for document in documents])
        if len(vectors) != len(documents):
            msg = "Embedding provider returned a different number of vectors than documents."
            raise ValueError(msg)
        if not vectors:
            return []

        # The embedding dimension is only knowable once we have real vectors, so
        # the typed, indexed table is provisioned lazily on first write.
        await self._ensure_embedding_table(len(vectors[0]))

        embedding = self._embedding_table()
        from sqlalchemy.dialects.postgresql import insert

        document_ids = (
            list(ids)
            if ids is not None
            else [str(document.id) if document.id is not None else str(uuid.uuid4()) for document in documents]
        )
        if len(document_ids) != len(documents):
            msg = "The number of document ids must match the number of documents."
            raise ValueError(msg)

        engine = self._ensure_async_engine()
        async with engine.begin() as conn:
            rows = [
                {
                    "id": document_id,
                    "embedding": vector,
                    "document": document.page_content,
                    "cmetadata": document.metadata,
                }
                for document_id, document, vector in zip(document_ids, documents, vectors, strict=True)
            ]
            statement = insert(embedding).values(rows)
            statement = statement.on_conflict_do_update(
                index_elements=[embedding.c.id],
                set_={
                    "embedding": statement.excluded.embedding,
                    "document": statement.excluded.document,
                    "cmetadata": statement.excluded.cmetadata,
                },
            )
            await conn.execute(statement)
        return document_ids

    async def _similarity_search(
        self,
        query: str,
        *,
        k: int,
        filter: dict[str, Any] | None = None,  # noqa: A002
    ) -> list[tuple[Document, float]]:
        await self.ensure_ready()
        if self.embedding_function is None:
            msg = "PostgresBackend requires an embedding function to search documents."
            raise ValueError(msg)
        query_vector = await self.embedding_function.aembed_query(query)

        embedding = self._embedding_table(len(query_vector))
        from sqlalchemy import select

        distance = embedding.c.embedding.cosine_distance(query_vector).label("distance")
        statement = (
            select(embedding.c.id, embedding.c.document, embedding.c.cmetadata, distance).order_by(distance).limit(k)
        )
        if filter:
            statement = statement.where(embedding.c.cmetadata.contains(filter))

        engine = self._ensure_async_engine()
        async with engine.connect() as conn:
            if not await self._table_exists(conn):
                return []  # nothing ingested yet — no table to scan
            rows = (await conn.execute(statement)).all()
        return [
            (
                Document(
                    id=str(row.id),
                    page_content=row.document or "",
                    metadata=dict(row.cmetadata or {}),
                ),
                float(row.distance),
            )
            for row in rows
        ]

    # ---- native metrics / lifecycle (override the base defaults) --------

    async def count(self) -> int:
        await self.ensure_ready()
        from sqlalchemy import text

        engine = self._ensure_async_engine()
        try:
            async with engine.connect() as conn:
                if not await self._table_exists(conn):
                    return 0
                value = await conn.scalar(text(_count_sql(self.table_name)))
            return int(value or 0)
        except Exception as exc:  # noqa: BLE001 — fresh KB: table may not exist yet
            await logger.awarning("Postgres count() failed for %s: %s", self.kb_name, exc)
            return 0

    async def iter_documents(
        self,
        *,
        batch_size: int = 5000,
        include_embeddings: bool = False,
    ) -> AsyncIterator[list[IngestedDocument]]:
        """Stream stored chunks via a psycopg3 server-side cursor (native async).

        ``conn.stream`` streams rows off a server-side cursor, applying backpressure
        so we never buffer the whole table — the async analogue of OpenSearch's
        scan-through-a-queue, with none of the thread/queue plumbing.
        """
        await self.ensure_ready()
        from sqlalchemy import text

        engine = self._ensure_async_engine()
        query = _iter_documents_sql(self.table_name, include_embeddings=include_embeddings)
        try:
            async with engine.connect() as conn:
                if not await self._table_exists(conn):
                    return
                result = await conn.stream(text(query))
                batch: list[IngestedDocument] = []
                async for row in result:
                    batch.append(
                        IngestedDocument(
                            content=row[0] or "",
                            metadata=dict(row[1] or {}),
                            embedding=_coerce_embedding(row[2]) if include_embeddings else None,
                        )
                    )
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
                if batch:
                    yield batch
        except Exception as exc:  # noqa: BLE001 — fresh KB: table may not exist yet
            await logger.awarning("Postgres iter_documents failed for %s: %s", self.kb_name, exc)

    async def delete_by(self, where: dict[str, Any]) -> None:
        """Delete chunks whose ``cmetadata`` contains ``where`` (JSONB @>)."""
        await self.ensure_ready()
        if not where:
            return
        from sqlalchemy import text

        engine = self._ensure_async_engine()
        try:
            async with engine.begin() as conn:
                if not await self._table_exists(conn):
                    return
                await conn.execute(text(_delete_by_sql(self.table_name)), {"where": json.dumps(where)})
        except Exception as exc:
            await logger.awarning("Postgres delete_by failed for %s: %s", self.kb_name, exc)
            raise

    async def storage_size_bytes(self) -> int:
        await self.ensure_ready()
        from sqlalchemy import text

        engine = self._ensure_async_engine()
        try:
            async with engine.connect() as conn:  # whole-table approximation
                value = await conn.scalar(text(_STORAGE_SIZE_SQL), {"name": self.table_name})
            return int(value or 0)
        except Exception as exc:  # noqa: BLE001 — table may not exist before first write
            await logger.awarning("Postgres storage_size_bytes failed for %s: %s", self.kb_name, exc)
            return 0

    async def delete_collection(self) -> None:
        await self.ensure_ready()
        from sqlalchemy import text

        engine = self._ensure_async_engine()
        try:
            async with engine.begin() as conn:  # drops the table + its indexes
                await conn.execute(text(_drop_table_sql(self.table_name)))
        except Exception as exc:
            await logger.awarning("Postgres delete_collection failed for %s: %s", self.kb_name, exc)
            raise

    async def test_connection(self) -> TestConnectionResult:
        """Native ``SELECT 1`` + verify the pgvector extension. No embeddings needed."""
        try:
            await self.ensure_ready()
        except ValueError as exc:
            return TestConnectionResult(ok=False, message=str(exc), details={"type": "ConfigError"})
        try:
            self._require_pgvector()
            engine = self._ensure_async_engine()
        except Exception as exc:  # noqa: BLE001 — normalize optional dependency and engine setup failures
            message = str(exc) if isinstance(exc, RuntimeError) else "Postgres backend setup failed."
            return TestConnectionResult(
                ok=False,
                message=message,
                details={"type": "SetupError", "error_type": type(exc).__name__},
            )
        from sqlalchemy import text

        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                ext_version = await conn.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
                server_version = await conn.scalar(text("SHOW server_version"))
        except Exception as exc:  # noqa: BLE001 — map driver errors to a friendly message
            return TestConnectionResult(
                ok=False,
                message=(
                    "Could not reach Postgres. Verify PGVECTOR_CONNECTION_STRING (host, port, credentials, network)."
                ),
                details={"type": type(exc).__name__, "error": str(exc)},
            )
        if not ext_version:
            return TestConnectionResult(
                ok=False,
                message=MISSING_EXTENSION_MESSAGE,
                details={"type": MISSING_EXTENSION_DETAILS_TYPE},
            )
        return TestConnectionResult(
            ok=True,
            message=f"Connected to Postgres {server_version or '?'} (pgvector {ext_version}).",
            details={"server_version": server_version or "", "pgvector_version": ext_version},
        )

    async def teardown(self) -> None:
        engine = getattr(self, "_pg_engine", None)
        if engine is not None:
            try:
                await engine.dispose()
            except Exception as exc:  # noqa: BLE001
                await logger.awarning("Postgres engine.dispose failed for %s: %s", self.kb_name, exc)
        self._pg_engine = None
        self._vector_store = None
