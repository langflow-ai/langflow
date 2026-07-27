"""Postgres (pgvector) vector-store backend.

Wraps ``langchain_postgres.PGVector`` so Langflow Knowledge Bases can target a
Postgres database with the ``pgvector`` extension. Unlike OpenSearch / Chroma
Cloud — which resolve per-KB credential *variable names* stored in
``backend_config`` — pgVector is **environment-variable driven**: a single
``PGVECTOR_CONNECTION_STRING`` on the server env configures the connection for
the whole deployment (every replica). No frontend configuration is required;
when the env var is present and reachable the deployment auto-defaults to
pgVector for new Knowledge Bases and Memory Bases.

Each KB/MB maps to its own pgvector collection, named after the KB
(``self.kb_name``) — multiple bases never share a collection.

The store is built in **async mode** (``async_mode=True``): construction does no
DB I/O, and the first ``aadd_documents`` / ``asimilarity_search`` call lazily
creates the ``vector`` extension + the ``langchain_pg_*`` tables on the async
engine LangChain manages internally (``base.py`` drives the async ``VectorStore``
API). Heavy metric reads (count / iter / delete / test) run on a separate
native-async sidecar engine over the same connection string.

``langchain_postgres`` declares ``pgvector<0.4``, which conflicts with Langflow's
security-pinned ``pgvector>=0.4.2`` (#12371). The two are runtime-compatible, so
the workspace ``[tool.uv] override-dependencies`` forces ``pgvector>=0.4.2`` past
that ceiling — keeping us on the maintained store rather than the sunset
``langchain-community`` PGVector.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from lfx.base.knowledge_bases.backends.base import (
    BackendType,
    BaseVectorStoreBackend,
    IngestedDocument,
    TestConnectionResult,
)
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langchain_core.vectorstores import VectorStore


# Single env var that configures pgVector for the whole deployment.
DEFAULT_CONNECTION_STRING_VARIABLE = "PGVECTOR_CONNECTION_STRING"
# Tables langchain_postgres.PGVector persists to (same names as the legacy
# community store). These are fixed schema identifiers (never user input) and
# are written as literals in the SQL below so every user value stays a bound
# parameter.
_EMBEDDING_TABLE = "langchain_pg_embedding"
_COLLECTION_TABLE = "langchain_pg_collection"

# Prebuilt SQL for the native metric/lifecycle reads. Interpolating only the
# fixed table-name constants above keeps the queries static (no S608 vector);
# ``:name`` / ``:where`` are always passed as bound parameters.
_COUNT_SQL = (
    f"SELECT count(*) FROM {_EMBEDDING_TABLE} e "  # noqa: S608 — fixed table names, bound params
    f"JOIN {_COLLECTION_TABLE} c ON e.collection_id = c.uuid WHERE c.name = :name"
)
_DELETE_BY_SQL = (
    f"DELETE FROM {_EMBEDDING_TABLE} "  # noqa: S608 — fixed table names, bound params
    f"WHERE collection_id = (SELECT uuid FROM {_COLLECTION_TABLE} WHERE name = :name) "
    "AND cmetadata @> CAST(:where AS jsonb)"
)
_DELETE_COLLECTION_SQL = f"DELETE FROM {_COLLECTION_TABLE} WHERE name = :name"  # noqa: S608 — fixed table name
_STORAGE_SIZE_SQL = f"SELECT pg_total_relation_size('{_EMBEDDING_TABLE}')"


def _iter_documents_sql(*, include_embeddings: bool) -> str:
    columns = "e.document, e.cmetadata" + (", e.embedding" if include_embeddings else "")
    return (
        f"SELECT {columns} FROM {_EMBEDDING_TABLE} e "  # noqa: S608 — fixed table names, bound params
        f"JOIN {_COLLECTION_TABLE} c ON e.collection_id = c.uuid WHERE c.name = :name"
    )


def _normalize_driver(url: str) -> str:
    """Force the psycopg3 driver the sync store + the async sidecar engine need."""
    if url.startswith("postgresql+psycopg://"):
        return url
    for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.split("://", 1)[1]
    return url


def read_connection_string_from_env(variable_name: str = DEFAULT_CONNECTION_STRING_VARIABLE) -> str | None:
    """Read the pgVector connection string from the server environment.

    Reads the process env directly (server-level config, not a tenant-supplied
    name); ``PGVECTOR_CONNECTION_STRING`` is not a ``safe_getenv``-reserved name.
    Powers the startup log and the auto-default check.
    """
    import os

    return os.getenv(variable_name) or None


def postgres_env_configured(variable_name: str = DEFAULT_CONNECTION_STRING_VARIABLE) -> bool:
    """Return True when pgVector is provisioned via env (the auto-default trigger)."""
    return bool(read_connection_string_from_env(variable_name))


def _coerce_embedding(raw: Any) -> list[float] | None:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        return [float(v) for v in raw]
    try:  # pgvector often round-trips as "[0.1,0.2,...]"
        return [float(v) for v in json.loads(str(raw))]
    except (ValueError, TypeError):
        return None


class PostgresBackend(BaseVectorStoreBackend):
    """Postgres + pgvector as a Langflow KB backend (environment-driven)."""

    backend_type = BackendType.POSTGRES

    # ---- config / secret resolution -------------------------------------

    async def _resolve_secrets(self) -> None:
        variable_name = self.backend_config.get("connection_string_variable") or DEFAULT_CONNECTION_STRING_VARIABLE
        # pgVector is environment-driven by design (server-level config, not a
        # per-tenant UI secret). Read the process env FIRST so the normal path
        # never queries the variable service — otherwise every resolution logs a
        # spurious "<VAR> variable not found" because the connection string lives
        # only in the environment, not the variables table. Fall back to the
        # variable service (via resolve_secret) only when the env var is unset,
        # covering deployments that deliberately store it as a Langflow variable.
        connection_string = read_connection_string_from_env(variable_name)
        if not connection_string:
            connection_string = await self.resolve_secret(variable_name)
        if not connection_string:
            msg = (
                f"PostgresBackend needs the {variable_name!r} environment variable populated with a "
                "Postgres connection string, e.g. "
                "'postgresql+psycopg://user:pass@host:5432/dbname'."  # pragma: allowlist secret
            )
            raise ValueError(msg)
        self._resolved_connection_string = _normalize_driver(connection_string)

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

    # ---- the one required method ----------------------------------------

    def _build_vector_store(self) -> VectorStore:
        connection_string = getattr(self, "_resolved_connection_string", None)
        if not connection_string:
            msg = "PostgresBackend.ensure_ready() must be awaited before _build_vector_store."
            raise RuntimeError(msg)
        try:
            from langchain_postgres import PGVector
        except ImportError as exc:
            msg = (
                "PostgresBackend requires the 'pgvector' package. "
                "Install the pgvector extra, e.g. pip install 'langflow[pgvector]'."
            )
            raise RuntimeError(msg) from exc
        try:
            # async_mode=True builds an async engine but performs NO DB I/O here;
            # the ``vector`` extension + langchain_pg_* tables are created lazily
            # on the first aadd_documents / asimilarity_search call. base.py only
            # ever drives the async VectorStore API (aadd_documents /
            # asimilarity_search*), and count/iter/delete/test are overridden
            # below with native-async raw SQL on a separate sidecar engine, so no
            # sync store method is ever invoked.
            return PGVector(
                embeddings=self.embedding_function,
                connection=connection_string,  # postgresql+psycopg:// — async-capable (psycopg3)
                collection_name=self.kb_name,  # one collection per KB / Memory Base
                use_jsonb=True,
                async_mode=True,
            )
        except ModuleNotFoundError as exc:  # pgvector client package missing
            msg = (
                "PostgresBackend requires the 'pgvector' package. "
                "Install the pgvector extra, e.g. pip install 'langflow[pgvector]'."
            )
            raise RuntimeError(msg) from exc

    # ---- native metrics / lifecycle (override the base defaults) --------

    async def count(self) -> int:
        await self.ensure_ready()
        from sqlalchemy import text

        engine = self._ensure_async_engine()
        try:
            async with engine.connect() as conn:
                value = await conn.scalar(text(_COUNT_SQL), {"name": self.kb_name})
            return int(value or 0)
        except Exception as exc:  # noqa: BLE001 — fresh KB: tables may not exist yet
            logger.warning("Postgres count() failed for %s: %s", self.kb_name, exc)
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
        query = _iter_documents_sql(include_embeddings=include_embeddings)
        try:
            async with engine.connect() as conn:
                result = await conn.stream(text(query), {"name": self.kb_name})
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
        except Exception as exc:  # noqa: BLE001
            logger.warning("Postgres iter_documents failed for %s: %s", self.kb_name, exc)

    async def delete_by(self, where: dict[str, Any]) -> None:
        """Delete chunks whose ``cmetadata`` contains ``where`` (JSONB @>)."""
        await self.ensure_ready()
        if not where:
            return
        from sqlalchemy import text

        engine = self._ensure_async_engine()
        try:
            async with engine.begin() as conn:
                await conn.execute(text(_DELETE_BY_SQL), {"name": self.kb_name, "where": json.dumps(where)})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Postgres delete_by failed for %s: %s", self.kb_name, exc)

    async def storage_size_bytes(self) -> int:
        await self.ensure_ready()
        from sqlalchemy import text

        engine = self._ensure_async_engine()
        try:
            async with engine.connect() as conn:  # whole-table approximation
                value = await conn.scalar(text(_STORAGE_SIZE_SQL))
            return int(value or 0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Postgres storage_size_bytes failed for %s: %s", self.kb_name, exc)
            return 0

    async def delete_collection(self) -> None:
        await self.ensure_ready()
        from sqlalchemy import text

        engine = self._ensure_async_engine()
        try:
            async with engine.begin() as conn:  # FK cascade removes the embeddings
                await conn.execute(text(_DELETE_COLLECTION_SQL), {"name": self.kb_name})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Postgres delete_collection failed for %s: %s", self.kb_name, exc)

    async def test_connection(self) -> TestConnectionResult:
        """Native ``SELECT 1`` + verify the pgvector extension. No embeddings needed."""
        try:
            await self.ensure_ready()
        except ValueError as exc:
            return TestConnectionResult(ok=False, message=str(exc), details={"type": "ConfigError"})
        from sqlalchemy import text

        engine = self._ensure_async_engine()
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
                message="Connected, but the 'vector' (pgvector) extension is not installed on this database.",
                details={"type": "MissingExtension"},
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
                logger.warning("Postgres engine.dispose failed for %s: %s", self.kb_name, exc)
        self._pg_engine = None
        self._vector_store = None
