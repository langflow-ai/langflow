"""Postgres (pgvector) vector-store backend.

The backend is configured by one deployment-level
``PGVECTOR_CONNECTION_STRING`` environment variable. Each Knowledge Base or
Memory Base maps to a stable, owner-qualified collection so users may safely use
the same display name.

The small async adapter below deliberately uses SQLAlchemy + ``pgvector``
directly. This keeps the published ``pgvector`` extra satisfiable while
preserving Langflow's security floor on the Python pgvector client; released
``langchain-postgres`` versions still require ``pgvector<0.4``.
"""

from __future__ import annotations

import hashlib
import json
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


# Single env var that configures pgVector for the whole deployment.
DEFAULT_CONNECTION_STRING_VARIABLE = "PGVECTOR_CONNECTION_STRING"
# Tables Langflow persists to using the conventional LangChain PGVector schema.
# These are fixed schema identifiers (never user input) and
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

    def _database_tables(self):
        """Build the conventional PGVector SQLAlchemy table definitions lazily."""
        tables = getattr(self, "_pg_tables", None)
        if tables is not None:
            return tables
        try:
            from pgvector.sqlalchemy import Vector
            from sqlalchemy import Column, ForeignKey, Index, MetaData, String, Table
            from sqlalchemy.dialects.postgresql import JSON, JSONB, UUID
        except (ImportError, RuntimeError) as exc:
            msg = (
                "PostgresBackend requires the 'pgvector' package. "
                "Install the pgvector extra, e.g. pip install 'langflow[pgvector]'."
            )
            raise RuntimeError(msg) from exc

        metadata = MetaData()
        collection = Table(
            _COLLECTION_TABLE,
            metadata,
            Column("uuid", UUID(as_uuid=True), primary_key=True),
            Column("name", String, nullable=False, unique=True),
            Column("cmetadata", JSON),
        )
        embedding = Table(
            _EMBEDDING_TABLE,
            metadata,
            Column("id", String, primary_key=True),
            Column(
                "collection_id",
                UUID(as_uuid=True),
                ForeignKey(f"{_COLLECTION_TABLE}.uuid", ondelete="CASCADE"),
            ),
            Column("embedding", Vector()),
            Column("document", String, nullable=True),
            Column("cmetadata", JSONB, nullable=True),
        )
        Index(
            "ix_cmetadata_gin",
            embedding.c.cmetadata,
            postgresql_using="gin",
            postgresql_ops={"cmetadata": "jsonb_path_ops"},
        )
        self._pg_tables = (metadata, collection, embedding)
        return self._pg_tables

    async def _ensure_store_ready(self) -> None:
        """Create the extension, shared tables, and this owner's collection."""
        await self.ensure_ready()
        metadata, collection, _embedding = self._database_tables()
        from sqlalchemy import text
        from sqlalchemy.dialects.postgresql import insert

        engine = self._ensure_async_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 1573678846307946496})
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(metadata.create_all)
            statement = (
                insert(collection)
                .values(uuid=uuid.uuid4(), name=self.collection_name, cmetadata={})
                .on_conflict_do_nothing(index_elements=[collection.c.name])
            )
            await conn.execute(statement)

    # ---- the one required method ----------------------------------------

    def _build_vector_store(self) -> VectorStore:
        return _PostgresVectorStore(self)

    async def _add_documents(self, documents: list[Document], *, ids: Sequence[str] | None = None) -> list[str]:
        await self._ensure_store_ready()
        if self.embedding_function is None:
            msg = "PostgresBackend requires an embedding function to add documents."
            raise ValueError(msg)
        vectors = await self.embedding_function.aembed_documents([document.page_content for document in documents])
        if len(vectors) != len(documents):
            msg = "Embedding provider returned a different number of vectors than documents."
            raise ValueError(msg)

        _metadata, collection, embedding = self._database_tables()
        from sqlalchemy import select
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
            collection_id = await conn.scalar(
                select(collection.c.uuid).where(collection.c.name == self.collection_name)
            )
            rows = [
                {
                    "id": document_id,
                    "collection_id": collection_id,
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
                    "collection_id": statement.excluded.collection_id,
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
        await self._ensure_store_ready()
        if self.embedding_function is None:
            msg = "PostgresBackend requires an embedding function to search documents."
            raise ValueError(msg)
        query_vector = await self.embedding_function.aembed_query(query)

        _metadata, collection, embedding = self._database_tables()
        from sqlalchemy import select

        distance = embedding.c.embedding.cosine_distance(query_vector).label("distance")
        statement = (
            select(embedding.c.id, embedding.c.document, embedding.c.cmetadata, distance)
            .join(collection, embedding.c.collection_id == collection.c.uuid)
            .where(collection.c.name == self.collection_name)
            .order_by(distance)
            .limit(k)
        )
        if filter:
            statement = statement.where(embedding.c.cmetadata.contains(filter))

        engine = self._ensure_async_engine()
        async with engine.connect() as conn:
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
                value = await conn.scalar(text(_COUNT_SQL), {"name": self.collection_name})
            return int(value or 0)
        except Exception as exc:  # noqa: BLE001 — fresh KB: tables may not exist yet
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
        query = _iter_documents_sql(include_embeddings=include_embeddings)
        try:
            async with engine.connect() as conn:
                result = await conn.stream(text(query), {"name": self.collection_name})
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
        except Exception as exc:  # noqa: BLE001 — fresh KB: tables may not exist yet
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
                await conn.execute(
                    text(_DELETE_BY_SQL),
                    {"name": self.collection_name, "where": json.dumps(where)},
                )
        except Exception as exc:
            await logger.awarning("Postgres delete_by failed for %s: %s", self.kb_name, exc)
            raise

    async def storage_size_bytes(self) -> int:
        await self.ensure_ready()
        from sqlalchemy import text

        engine = self._ensure_async_engine()
        try:
            async with engine.connect() as conn:  # whole-table approximation
                value = await conn.scalar(text(_STORAGE_SIZE_SQL))
            return int(value or 0)
        except Exception as exc:  # noqa: BLE001 — table may not exist before first write
            await logger.awarning("Postgres storage_size_bytes failed for %s: %s", self.kb_name, exc)
            return 0

    async def delete_collection(self) -> None:
        await self.ensure_ready()
        from sqlalchemy import text

        engine = self._ensure_async_engine()
        try:
            async with engine.begin() as conn:  # FK cascade removes the embeddings
                await conn.execute(text(_DELETE_COLLECTION_SQL), {"name": self.collection_name})
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
            self._database_tables()
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
                await logger.awarning("Postgres engine.dispose failed for %s: %s", self.kb_name, exc)
        self._pg_engine = None
        self._vector_store = None
        self._pg_tables = None
