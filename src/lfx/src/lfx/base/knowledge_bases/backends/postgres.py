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

import asyncio
import hashlib
import json
import os
import re
import uuid
import weakref
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

from lfx.base.knowledge_bases.backends.base import (
    BackendConfigurationError,
    BackendType,
    BaseVectorStoreBackend,
    IngestedDocument,
    TestConnectionResult,
)
from lfx.base.knowledge_bases.backends.naming import owner_scoped_collection_name
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from sqlalchemy.ext.asyncio import AsyncConnection


# Single env var that configures pgVector for the whole deployment.
DEFAULT_CONNECTION_STRING_VARIABLE = "PGVECTOR_CONNECTION_STRING"

# Collection tables (with their indexes) this process has verified as fully
# provisioned, keyed by (connection string, table, dimension). Writes check the
# catalog only on a miss, so steady-state ingestion runs no DDL and takes no lock.
# An entry is dropped when the table is dropped here, and when a write finds the
# table missing or retyped (dropped or recreated by another process).
_READY_TABLES: set[tuple[str, str, int]] = set()

# One async engine (one connection pool) per event loop, process and connection
# string, shared by every backend instance. Ingestion creates a backend per job;
# sharing the engine lets those jobs reuse pooled connections. ``max_overflow=-1``
# puts no limit on concurrent connections, and up to ``pool_size`` idle
# connections stay open for reuse.
#
# Backends run on the caller's event loop. The KB API, ingestion jobs and flow
# runs in the server (including the Knowledge component as an agent tool) all
# await them on the server loop, so each server process keeps one pool. A flow
# run from a temporary loop (``run_until_complete``, ``asyncio.run`` or
# ``Graph.start`` in a script) gets its own engine and pool. Once that loop is
# closed and collected its entry is dropped, and the garbage collector closes its
# connections without ``dispose()``. A new synchronous caller awaits the async
# API on its own loop, or pops its loop's engines and awaits ``dispose()``
# before that loop closes.
_ENGINES: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[tuple[int, str], Any]] = weakref.WeakKeyDictionary()
_ENGINE_POOL_SIZE = 5


def _shared_engine(connection_string: str):
    """Return this event loop's engine for ``connection_string``, creating it once."""
    from sqlalchemy.ext.asyncio import create_async_engine

    loop = asyncio.get_running_loop()
    engines = _ENGINES.setdefault(loop, {})
    key = (os.getpid(), connection_string)  # a forked child must not reuse the parent's sockets
    engine = engines.get(key)
    if engine is None:
        engine = create_async_engine(
            connection_string, pool_pre_ping=True, pool_size=_ENGINE_POOL_SIZE, max_overflow=-1
        )
        engines[key] = engine
    return engine


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

# pgvector added iterative index scans in 0.8.0. Before then, a metadata filter
# is applied only to the fixed HNSW candidate window (``hnsw.ef_search``), so a
# selective filter can return fewer than ``k`` rows. See ``_widen_filtered_scan``.
_ITERATIVE_SCAN_MIN_VERSION = (0, 8, 0)
# pgvector's default HNSW candidate window; we widen it for filtered queries.
_HNSW_DEFAULT_EF_SEARCH = 40
# Filtered queries scan ``k * this`` candidates (capped) so a post-scan metadata
# filter has a much larger pool to match against even on pre-0.8 servers.
_FILTER_EF_SEARCH_MULTIPLIER = 40
_FILTER_EF_SEARCH_CAP = 1000

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
# Structured ``details.type`` tag on the test-connection result. The frontend
# renders only ``ok`` + ``message`` today; this tag is carried in the response's
# optional ``details`` bag so a future UI can key off it for extension-specific
# hints without re-parsing the message text.
MISSING_EXTENSION_DETAILS_TYPE = "MissingExtension"

# Per-collection tables mean the connecting role needs CREATE on the schema at
# first ingest. ``test_connection`` verifies this so the operator learns at
# configure time, not when the first ingest fails with a raw permission error.
MISSING_CREATE_PRIVILEGE_MESSAGE = (
    "Connected to Postgres, but this role cannot create tables in the current schema. "
    "Langflow creates one table per knowledge base on first ingest, so it needs CREATE on the schema. "
    "Grant it (for example `GRANT CREATE ON SCHEMA public TO <role>;`) or point "
    "PGVECTOR_CONNECTION_STRING at a role and schema that already has it."
)
MISSING_CREATE_PRIVILEGE_DETAILS_TYPE = "MissingCreatePrivilege"


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
    columns = "id, document, cmetadata" + (", embedding" if include_embeddings else "")
    return f"SELECT {columns} FROM {_validate_table_name(table)}"  # noqa: S608 — table name validated above


def _ddl_lock_key(table: str) -> int:
    """Advisory-lock key that serializes DDL for one collection table.

    Only concurrent bootstraps of the *same* table need to be serialized (two
    ``CREATE TABLE IF NOT EXISTS`` of one name can race in the catalog), so each
    table gets its own key and different collections never wait on each other.
    """
    digest = hashlib.sha256(f"langflow-kb-ddl:{_validate_table_name(table)}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


# One round trip that reports everything the bootstrap needs. ``to_regclass``
# resolves names through ``search_path``, matching where the DDL creates them.
_CATALOG_STATE_SQL = (
    "SELECT "
    "(SELECT extversion FROM pg_extension WHERE extname = 'vector') AS extversion, "
    "(SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
    "WHERE a.attrelid = to_regclass(:table) AND a.attname = 'embedding' "
    "AND a.attnum > 0 AND NOT a.attisdropped) AS embedding_type, "
    "to_regclass(:table) IS NOT NULL AS has_table, "
    "to_regclass(:gin_index) IS NOT NULL AS has_gin_index, "
    "to_regclass(:hnsw_index) IS NOT NULL AS has_hnsw_index"
)


@dataclass(frozen=True)
class _CatalogState:
    """What already exists for one collection table."""

    extversion: str | None
    has_table: bool
    existing_dim: int | None
    has_gin_index: bool
    has_hnsw_index: bool


def _is_stale_table_error(exc: BaseException) -> bool:
    """True when a write failed because the table changed since it was verified.

    ``42P01`` (undefined_table) means it was dropped; pgvector's
    ``expected N dimensions`` means it was recreated for another model.
    """
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None)
    if sqlstate == "42P01":
        return True
    return bool(re.search(r"expected \d+ dimensions, not \d+", str(orig if orig is not None else exc)))


def _parse_vector_dim(type_str: str | None) -> int | None:
    """Extract N from a ``vector(N)`` Postgres type string."""
    match = re.search(r"vector\((\d+)\)", type_str or "")
    return int(match.group(1)) if match else None


def _parse_pgvector_version(raw: str | None) -> tuple[int, ...] | None:
    """Parse a pgvector ``extversion`` string (e.g. ``"0.8.0"``) into a tuple.

    Returns ``None`` when the value is missing or unparseable, so callers treat
    an unknown version conservatively (assume the older behavior).
    """
    match = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(raw or ""))
    if not match:
        return None
    return tuple(int(group) if group else 0 for group in match.groups())


def _dimension_mismatch_message(kb_name: str, *, existing_dim: int, model_dim: int) -> str:
    """The single operator-facing message for an embedding-width mismatch.

    Shared by ingest (``_ensure_embedding_table``) and retrieval
    (``_translate_dimension_error``) so both surface the exact same guidance.
    """
    return (
        f"Knowledge base '{kb_name}' was created with {existing_dim}-dimensional embeddings, "
        f"but the current embedding model produces {model_dim}. Recreate the knowledge base or "
        "restore the original embedding model."
    )


def _translate_dimension_error(exc: Exception, *, kb_name: str, query_dim: int) -> str | None:
    """Translate pgvector's raw dimension-mismatch error into the shared message.

    Returns the operator-facing message (identical to ingest's) when ``exc`` is a
    ``different vector dimensions N and M`` error, else ``None``. Parsing the
    numbers out of the driver message — rather than issuing an extra catalog
    probe on every search — keeps the retrieval happy path free of a round-trip;
    the translation only runs once a query has already failed on the mismatch.
    """
    match = re.search(r"different vector dimensions (\d+) and (\d+)", str(exc))
    if not match:
        return None
    dims = {int(match.group(1)), int(match.group(2))}
    existing = next((dim for dim in sorted(dims) if dim != query_dim), None)
    if existing is None:
        return None
    return _dimension_mismatch_message(kb_name, existing_dim=existing, model_dim=query_dim)


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
    return BackendType.POSTGRES.value if postgres_env_configured() else BackendType.SQLITE.value


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
        """Capture the PostgreSQL backend exposed by this vector-store facade."""
        self._backend = backend

    @property
    def embeddings(self):
        """Expose the configured embedding function."""
        return self._backend.embedding_function

    @classmethod
    def from_texts(cls, *args, **kwargs):
        """Reject construction that bypasses the PostgreSQL backend configuration."""
        msg = "PostgresVectorStore must be constructed through PostgresBackend."
        raise NotImplementedError(msg)

    def similarity_search(self, *args, **kwargs):
        """Reject synchronous search in the asynchronous PostgreSQL facade."""
        msg = "Use the async PostgresVectorStore search methods."
        raise NotImplementedError(msg)

    async def aadd_documents(self, documents: list[Document], **kwargs: Any) -> list[str]:
        """Write documents through the PostgreSQL backend and return their IDs."""
        return await self._backend._add_documents(documents, ids=kwargs.get("ids"))  # noqa: SLF001

    async def asimilarity_search(
        self,
        query: str,
        k: int = 4,
        *,
        filter: dict[str, Any] | None = None,  # noqa: A002
        **kwargs: Any,  # noqa: ARG002
    ) -> list[Document]:
        """Return matching documents from the native asynchronous query."""
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
        """Return matching documents together with their native distances."""
        return await self._backend._similarity_search(query, k=k, filter=filter)  # noqa: SLF001


class PostgresBackend(BaseVectorStoreBackend):
    """Postgres + pgvector as a Langflow KB backend (environment-driven)."""

    distance_metric = "cosine"  # the HNSW index is built with vector_cosine_ops

    backend_type = BackendType.POSTGRES

    # ---- config / secret resolution -------------------------------------

    async def _resolve_secrets(self) -> None:
        # Never honor a backend_config-provided environment-variable name here:
        # backend_config is tenant-controlled, while this credential belongs to
        # the deployment.
        """Resolve the configured database URL using the backend credential policy."""
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
    def store_location(self) -> tuple[Any, ...]:
        """The resolved database and this KB's table."""
        return (self._resolved_connection_string, self.table_name)

    @property
    def collection_name(self) -> str:
        """Return a stable, non-identifying collection name scoped to the owner."""
        owner_id = self._coerce_user_uuid()
        if owner_id is None:
            msg = "PostgresBackend requires a valid user_id to isolate its collection."
            raise ValueError(msg)
        return owner_scoped_collection_name(owner_id, self.kb_name)

    @property
    def table_name(self) -> str:
        """Physical embedding table for this collection (validated for SQL use)."""
        return _validate_table_name(self.collection_name)

    def _ensure_async_engine(self):
        """Return the async engine used for writes, count/scan/delete and ping.

        Inside a running event loop this is the process-wide engine for this
        loop and connection string, so jobs reuse pooled connections instead of
        building and disposing an engine each.
        """
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
        try:
            engine = _shared_engine(connection_string)
            self._pg_engine_shared = True
        except RuntimeError:  # no running event loop: an engine of this instance's own
            engine = create_async_engine(connection_string, pool_pre_ping=True)
            self._pg_engine_shared = False
        self._pg_engine = engine
        return engine

    async def _execute_write(self, statement: Any) -> None:
        """Run one write statement on its own, without an explicit transaction.

        A single statement is atomic in autocommit mode, and the database never
        holds the connection idle in a transaction while the client is busy.
        """
        engine = self._ensure_async_engine()
        async with engine.connect() as conn:
            autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await autocommit.execute(statement)

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

    def _ready_key(self, dim: int) -> tuple[str, str, int]:
        return (getattr(self, "_resolved_connection_string", "") or "", self.table_name, int(dim))

    def _forget_ready_table(self) -> None:
        """Drop every memo entry for this collection table (any dimension)."""
        connection_string = getattr(self, "_resolved_connection_string", "") or ""
        table = self.table_name
        for key in [key for key in _READY_TABLES if key[0] == connection_string and key[1] == table]:
            _READY_TABLES.discard(key)

    async def _catalog_state(self, conn: AsyncConnection) -> _CatalogState:
        """Read the extension, table, column type and both indexes in one query."""
        from sqlalchemy import text

        table = self.table_name
        row = (
            await conn.execute(
                text(_CATALOG_STATE_SQL),
                {"table": table, "gin_index": f"{table}_cmeta_gin", "hnsw_index": f"{table}_hnsw"},
            )
        ).one()
        return _CatalogState(
            extversion=row.extversion,
            has_table=bool(row.has_table),
            existing_dim=_parse_vector_dim(row.embedding_type),
            has_gin_index=bool(row.has_gin_index),
            has_hnsw_index=bool(row.has_hnsw_index),
        )

    def _check_catalog_state(self, state: _CatalogState, dim: int) -> bool:
        """Raise on an unusable database or table; return True when nothing is missing."""
        # Operator owns the extension; Langflow verifies, never creates it.
        if not state.extversion:
            raise BackendConfigurationError(MISSING_EXTENSION_MESSAGE)
        # ``CREATE TABLE IF NOT EXISTS`` never alters an existing table, so a
        # model whose dimension differs from the one this KB was created with
        # would fail obscurely on INSERT. Surface it clearly instead.
        if state.has_table and state.existing_dim is not None and state.existing_dim != dim:
            raise BackendConfigurationError(
                _dimension_mismatch_message(self.kb_name, existing_dim=state.existing_dim, model_dim=dim)
            )
        return state.has_table and state.has_gin_index and (state.has_hnsw_index or dim > _HNSW_MAX_DIM)

    async def _ensure_embedding_table(self, dim: int) -> None:
        """Make sure this collection's typed, indexed table exists (idempotent).

        Once a process has verified a (table, dimension) it skips the database
        entirely. Otherwise one lock-free catalog query checks the table, its
        column type and both indexes; only when something is missing does it
        take this table's advisory lock, re-check, and create what is missing.
        ``CREATE INDEX IF NOT EXISTS`` takes a SHARE lock on the table before it
        checks for the index, so it would wait for in-flight inserts; it is
        therefore only issued for an index that does not exist. The HNSW and GIN
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
        ready_key = self._ready_key(dim)
        if ready_key in _READY_TABLES:
            return
        from sqlalchemy import text

        engine = self._ensure_async_engine()
        async with engine.connect() as conn:
            if self._check_catalog_state(await self._catalog_state(conn), dim):
                _READY_TABLES.add(ready_key)
                return

        async with engine.begin() as conn:
            await conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ddl_lock_key(table)})
            # Another process may have finished the bootstrap while we waited.
            state = await self._catalog_state(conn)
            self._check_catalog_state(state, dim)
            if not state.has_table:
                await conn.execute(
                    text(
                        f'CREATE TABLE IF NOT EXISTS "{table}" ('
                        "id VARCHAR PRIMARY KEY, "
                        f"embedding vector({dim}), "
                        "document VARCHAR, "
                        "cmetadata JSONB)"
                    )
                )
            if not state.has_gin_index:
                await conn.execute(
                    text(
                        f'CREATE INDEX IF NOT EXISTS "{table}_cmeta_gin" ON "{table}" '
                        "USING gin (cmetadata jsonb_path_ops)"
                    )
                )
            if dim <= _HNSW_MAX_DIM:
                if not state.has_hnsw_index:
                    await conn.execute(
                        text(
                            f'CREATE INDEX IF NOT EXISTS "{table}_hnsw" ON "{table}" '
                            "USING hnsw (embedding vector_cosine_ops)"
                        )
                    )
            elif not state.has_table:
                await logger.awarning(
                    "pgvector cannot HNSW-index %d-dimensional embeddings (max %d) for %s; "
                    "similarity search will use an exact scan.",
                    dim,
                    _HNSW_MAX_DIM,
                    self.kb_name,
                )
        _READY_TABLES.add(ready_key)

    async def _table_exists(self, conn: AsyncConnection) -> bool:
        """Check whether the configured PostgreSQL vector table exists."""
        from sqlalchemy import text

        return (await conn.scalar(text("SELECT to_regclass(:name)"), {"name": self.table_name})) is not None

    async def _pgvector_extversion(self, conn: AsyncConnection) -> str | None:
        """Return the installed pgvector ``extversion`` (e.g. ``"0.8.0"``) or None."""
        from sqlalchemy import text

        return await conn.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))

    async def _widen_filtered_scan(self, conn: AsyncConnection, *, k: int) -> None:
        """Best-effort mitigation for pgvector's post-filter HNSW recall gap.

        pgvector evaluates a metadata ``WHERE`` filter only *after* the
        approximate HNSW scan has produced its candidate window
        (``hnsw.ef_search``, default 40). A highly selective filter — e.g. a
        single ``session_id`` in a Memory Base that stores every session — can
        fall entirely outside that window, so ``ORDER BY embedding <=> $1 ...
        LIMIT k`` returns fewer than ``k`` rows (sometimes zero) even though many
        matching rows exist. The effect is planner-dependent, so it can pass in
        dev and regress silently as the table grows.

        Two transaction-scoped mitigations, applied together:

        * pgvector >= 0.8.0: enable iterative index scans so the executor keeps
          pulling candidates from the index until it has ``k`` rows that satisfy
          the filter. This is the real fix, but it needs a *server-side*
          extension >= 0.8.0 — the pinned client floor (``pgvector>=0.4.2``)
          does not imply it, hence the version probe.
        * Always widen ``hnsw.ef_search`` for the filtered query so even a server
          that cannot iterate searches a far larger candidate pool before
          filtering.

        Both use ``SET LOCAL`` so they never outlive this query's transaction.
        """
        from sqlalchemy import text

        # ef_search is a bounded int computed here, never user input.
        ef_search = min(_FILTER_EF_SEARCH_CAP, max(_HNSW_DEFAULT_EF_SEARCH, k * _FILTER_EF_SEARCH_MULTIPLIER))
        await conn.execute(text(f"SET LOCAL hnsw.ef_search = {int(ef_search)}"))
        version = _parse_pgvector_version(await self._pgvector_extversion(conn))
        if version is not None and version >= _ITERATIVE_SCAN_MIN_VERSION:
            await conn.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))

    # ---- the one required method ----------------------------------------

    def _build_vector_store(self) -> VectorStore:
        """Create the asynchronous vector-store facade for this backend."""
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

        document_ids = (
            list(ids)
            if ids is not None
            else [str(document.id) if document.id is not None else str(uuid.uuid4()) for document in documents]
        )
        if len(document_ids) != len(documents):
            msg = "The number of document ids must match the number of documents."
            raise ValueError(msg)
        await self._upsert_rows(
            document_ids,
            [document.page_content for document in documents],
            [document.metadata for document in documents],
            vectors,
        )
        return document_ids

    async def _write_embedded(self, ids: list[str], docs: list[IngestedDocument]) -> None:
        await self._upsert_rows(
            ids,
            [doc.content for doc in docs],
            [doc.metadata for doc in docs],
            [doc.embedding for doc in docs],  # type: ignore[misc]  # validated non-empty by the caller
        )

    async def _upsert_rows(
        self,
        ids: list[str],
        contents: list[str],
        metadatas: list[dict[str, Any]],
        vectors: list[list[float]],
    ) -> None:
        """Upsert rows keyed by id. Shared by the embedding and precomputed-vector writes."""
        # The embedding dimension is only knowable once we have real vectors, so
        # the typed, indexed table is provisioned lazily on first write. After
        # the first verification this process skips the catalog entirely.
        dim = len(vectors[0])
        await self._ensure_embedding_table(dim)

        embedding = self._embedding_table()
        from sqlalchemy.dialects.postgresql import insert

        rows = [
            {"id": row_id, "embedding": vector, "document": content, "cmetadata": metadata}
            for row_id, content, metadata, vector in zip(ids, contents, metadatas, vectors, strict=True)
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

        try:
            await self._execute_write(statement)
        except Exception as exc:
            # The memo can be stale when another process dropped the table or
            # recreated it for another model. Re-verify (which recreates a
            # missing table or reports the dimension change) and retry once.
            if not _is_stale_table_error(exc):
                raise
            self._forget_ready_table()
            await self._ensure_embedding_table(dim)
            await self._execute_write(statement)

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
            if filter:
                # pgvector applies the metadata filter only after the approximate
                # HNSW scan, so a selective filter (e.g. a single session_id in a
                # Memory Base holding every session) can slip past the candidate
                # window and return < k rows — silently dropping matches. Widen
                # the scan (and iterate where the server supports it) first.
                await self._widen_filtered_scan(conn, k=k)
            try:
                rows = (await conn.execute(statement)).all()
            except Exception as exc:
                # A table built for a different embedding width otherwise leaks
                # the raw driver error; surface the same clear message ingest does.
                friendly = _translate_dimension_error(exc, kb_name=self.kb_name, query_dim=len(query_vector))
                if friendly is not None:
                    raise BackendConfigurationError(friendly) from exc
                raise
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
        """Count rows in the vector table, treating an unprovisioned table as empty."""
        await self.ensure_ready()
        from sqlalchemy import text

        engine = self._ensure_async_engine()
        # The only expected "empty" case — a KB with no table yet — is handled by
        # the explicit ``_table_exists`` check. A genuine failure (network drop,
        # ``permission denied``) is allowed to propagate rather than masquerade as
        # "0 chunks"; every caller of ``count()`` already treats it best-effort.
        async with engine.connect() as conn:
            if not await self._table_exists(conn):
                return 0
            value = await conn.scalar(text(_count_sql(self.table_name)))
        return int(value or 0)

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
        # As with ``count()``: the "no table yet" case is handled explicitly, so a
        # real streaming failure propagates instead of silently yielding nothing
        # (which would read as an empty KB / data loss to the caller).
        async with engine.connect() as conn:
            if not await self._table_exists(conn):
                return
            result = await conn.stream(text(query))
            batch: list[IngestedDocument] = []
            async for row in result:
                batch.append(
                    IngestedDocument(
                        content=row[1] or "",
                        metadata=dict(row[2] or {}),
                        embedding=_coerce_embedding(row[3]) if include_embeddings else None,
                        id=row[0],
                    )
                )
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
            if batch:
                yield batch

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
        """Estimate PostgreSQL table storage size without calling the embedding provider."""
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
        """Drop the configured vector table and its indexes."""
        await self.ensure_ready()
        from sqlalchemy import text

        engine = self._ensure_async_engine()
        try:
            async with engine.begin() as conn:  # drops the table + its indexes
                await conn.execute(text(_drop_table_sql(self.table_name)))
            self._forget_ready_table()
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

        can_create: bool | None = None
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                ext_version = await conn.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
                server_version = await conn.scalar(text("SHOW server_version"))
                if ext_version:
                    # Per-collection tables mean this role must be able to CREATE
                    # in the target schema at first ingest. Probe it now so a
                    # missing grant is reported here, not as a raw permission
                    # error on the first ingest. Advisory only — a probe failure
                    # leaves it unknown rather than failing the whole check.
                    try:
                        can_create = await conn.scalar(text("SELECT has_schema_privilege(current_schema(), 'CREATE')"))
                    except Exception as exc:  # noqa: BLE001 — privilege probe is best-effort
                        await logger.adebug("CREATE-privilege probe failed for %s: %s", self.kb_name, exc)
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
        if can_create is False:
            return TestConnectionResult(
                ok=False,
                message=MISSING_CREATE_PRIVILEGE_MESSAGE,
                details={"type": MISSING_CREATE_PRIVILEGE_DETAILS_TYPE},
            )
        return TestConnectionResult(
            ok=True,
            message=f"Connected to Postgres {server_version or '?'} (pgvector {ext_version}).",
            details={"server_version": server_version or "", "pgvector_version": ext_version},
        )

    async def teardown(self) -> None:
        """Dispose this backend's engine and drop its vector-store facade."""
        engine = getattr(self, "_pg_engine", None)
        # The shared engine outlives this instance; only an engine of its own is disposed.
        if engine is not None and not getattr(self, "_pg_engine_shared", False):
            try:
                await engine.dispose()
            except Exception as exc:  # noqa: BLE001
                await logger.awarning("Postgres engine.dispose failed for %s: %s", self.kb_name, exc)
        self._pg_engine = None
        self._pg_engine_shared = False
        self._vector_store = None
