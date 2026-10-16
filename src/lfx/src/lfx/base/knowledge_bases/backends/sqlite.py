"""Persistent, exact-search SQLite knowledge base storage.

APSW owns a private SQLite runtime. Canonical vectors live in ordinary tables,
so the vector extension is replaceable without rewriting user data. Connections
never escape a synchronous worker operation. The application must additionally
hold its whole-KB lifecycle guard when migrating or deleting a generation.
"""

from __future__ import annotations

import asyncio
import contextlib
import heapq
import json
import math
import os
import struct
import sys
import weakref
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from numbers import Real
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID, uuid4

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

from lfx.base.knowledge_bases.backends.base import (
    BackendConfigurationError,
    BackendType,
    BaseVectorStoreBackend,
    IngestedDocument,
    TestConnectionResult,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterable, Iterator

    from langchain_core.embeddings import Embeddings
    from numpy.typing import NDArray

_T = TypeVar("_T")
_SCHEMA_VERSION = 2
_MAX_MIGRATION_DIMENSIONS = 32768
_NATIVE_MIN_NONZERO_COMPONENT = 1e-8
_NATIVE_MAX_SQUARED_NORM = 1e24
_WORKERS = 4
_EXECUTOR = ThreadPoolExecutor(max_workers=_WORKERS, thread_name_prefix="kb-sqlite")
_EXECUTOR_PID = os.getpid()
_LOOP_LIMITS: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_HEADER_KEYS = (
    "schema_version",
    "store_id",
    "owner_id",
    "kb_id",
    "generation",
    "dimension",
    "metric",
    "model_fingerprint",
    "lifecycle",
)
_SCHEMA = """
CREATE TABLE IF NOT EXISTS store_header (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    schema_version INTEGER NOT NULL,
    store_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    kb_id TEXT NOT NULL,
    generation INTEGER NOT NULL CHECK(generation > 0),
    dimension INTEGER CHECK(dimension > 0),
    metric TEXT NOT NULL CHECK(metric IN ('l2', 'cosine', 'ip')),
    model_fingerprint TEXT,
    lifecycle TEXT NOT NULL CHECK(lifecycle IN ('active', 'deleted'))
);
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT NOT NULL CHECK(json_valid(metadata) AND json_type(metadata) = 'object'),
    vector BLOB NOT NULL,
    dimension INTEGER NOT NULL CHECK(dimension > 0 AND length(vector) = 4 * dimension),
    job_id TEXT,
    session_id TEXT,
    native_distance_safe INTEGER NOT NULL CHECK(native_distance_safe IN (0,1))
);
CREATE INDEX IF NOT EXISTS chunks_job ON chunks(job_id);
CREATE INDEX IF NOT EXISTS chunks_session ON chunks(session_id);
CREATE TABLE IF NOT EXISTS source_filter_values (
    document_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value_text TEXT NOT NULL,
    PRIMARY KEY(document_id, key, value_text)
);
CREATE INDEX IF NOT EXISTS source_filter_lookup ON source_filter_values(key, value_text, document_id);
CREATE TABLE IF NOT EXISTS migration_manifest (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    manifest TEXT NOT NULL CHECK(json_valid(manifest) AND json_type(manifest) = 'object')
);
"""


def _worker_executor() -> ThreadPoolExecutor:
    # A prefork server may already have used the parent's pool. Its threads do
    # not survive fork, and shutting down that inherited pool can deadlock.
    """Reuse the bounded executor that owns blocking SQLite operations."""
    global _EXECUTOR, _EXECUTOR_PID  # noqa: PLW0603 - process-private runtime
    if os.getpid() != _EXECUTOR_PID:
        _EXECUTOR = ThreadPoolExecutor(max_workers=_WORKERS, thread_name_prefix="kb-sqlite")
        _EXECUTOR_PID = os.getpid()
        _LOOP_LIMITS.clear()
    return _EXECUTOR


@dataclass(frozen=True)
class SQLiteStorageContext:
    """Trusted application routing, never populated from arbitrary request config."""

    root: Path
    owner_id: UUID
    kb_id: UUID
    generation: int = 1

    def __post_init__(self) -> None:
        # The administrator's root can have canonical OS aliases among its
        # ancestors (macOS /var -> /private/var). Resolve those only. Keep the
        # root itself and all generated children subject to symlink rejection.
        """Validate the absolute root, immutable UUIDs and positive storage generation."""
        root = Path(self.root).absolute()
        object.__setattr__(self, "root", root.parent.resolve() / root.name)
        object.__setattr__(self, "owner_id", UUID(str(self.owner_id)))
        object.__setattr__(self, "kb_id", UUID(str(self.kb_id)))
        if type(self.generation) is not int or self.generation < 1:
            msg = "SQLite storage generation must be a positive integer"
            raise BackendConfigurationError(msg)

    @property
    def database_path(self) -> Path:
        """Derive the database location from owner, KB UUID and generation."""
        return self.root / "sqlite" / str(self.owner_id) / str(self.kb_id) / str(self.generation) / "vectors.sqlite3"


def _json(value: Any) -> str:
    """Serialize bounded, finite JSON for durable SQLite metadata."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _metadata_json(metadata: dict[str, Any]) -> str:
    """Serialize metadata only after verifying its structure and size limits."""

    def validate(value: Any) -> None:
        """Reject nested metadata objects with non-string keys."""
        if isinstance(value, dict):
            if any(not isinstance(key, str) for key in value):
                msg = "SQLite metadata object keys must be strings"
                raise BackendConfigurationError(msg)
            for nested in value.values():
                validate(nested)
        elif isinstance(value, list):
            for nested in value:
                validate(nested)
        elif value is not None and not isinstance(value, (str, int, float, bool)):
            msg = "SQLite metadata must contain JSON values"
            raise BackendConfigurationError(msg)

    validate(metadata)
    try:
        # Keep object insertion order: historical filters stringify nested objects.
        return json.dumps(metadata, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        msg = "SQLite metadata must contain finite JSON values"
        raise BackendConfigurationError(msg) from exc


def _vector_blob(vector: Iterable[float] | None, *, metric: str) -> tuple[bytes, int]:
    """Encode a finite, dimension-checked vector in the storage format."""
    try:
        if vector is None:
            raise ValueError
        values = list(vector)
        if not values or any(isinstance(value, bool) or not isinstance(value, Real) for value in values):
            raise ValueError
        if not all(math.isfinite(value) for value in values):
            raise ValueError
        blob = struct.pack(f"<{len(values)}f", *values)
        # Overflow can also occur through under/overflow of a provider's dtype.
        canonical = struct.unpack(f"<{len(values)}f", blob)
        if not all(math.isfinite(value) for value in canonical):
            raise ValueError
        if metric == "cosine" and not any(canonical):
            msg = "Cosine distance is undefined for a zero vector"
            raise BackendConfigurationError(msg)
    except (TypeError, ValueError, OverflowError, struct.error) as exc:
        msg = "Embedding must be a nonempty finite float32 vector (nonzero for cosine)"
        raise BackendConfigurationError(msg) from exc
    return blob, len(values)


def _native_distance_safe(blob: bytes) -> bool:
    """Keep sqlite-vec's float32 intermediates far from overflow and underflow.

    sqlite-vec 0.1.9 accumulates squares/dot products in float32. A finite
    float32 input alone is insufficient: for example, squaring 1e30 overflows,
    and squaring 1e-30 underflows. These conservative bounds also keep the
    smallest nonzero difference between two accepted float32 components away
    from float32 underflow. Ordinary embedding vectors use the native path.
    The bit is a rebuildable projection of the canonical vector, not a vector
    transformation or a restriction on accepted finite legacy data.
    """
    values = struct.unpack(f"<{len(blob) // 4}f", blob)
    return (
        all(value == 0.0 or abs(value) >= _NATIVE_MIN_NONZERO_COMPONENT for value in values)
        and math.fsum(value * value for value in values) <= _NATIVE_MAX_SQUARED_NORM
    )


def _stable_distance_function(query_blob: bytes, *, metric: str) -> Callable[[bytes], float]:
    """Create a bounded one-row double precision fallback for extreme vectors."""
    dimension = len(query_blob) // 4
    query = struct.unpack(f"<{dimension}f", query_blob)
    query_norm = math.hypot(*query) if metric == "cosine" else 0.0

    def distance(stored_blob: bytes) -> float:
        """Compute the configured distance from a stored float32 vector to the query."""
        stored = struct.unpack(f"<{dimension}f", stored_blob)
        if metric == "l2":
            return math.dist(stored, query)
        stored_norm = math.hypot(*stored)
        if not stored_norm or not query_norm:
            msg = "Cosine distance is undefined for a zero vector"
            raise BackendConfigurationError(msg)
        cosine = math.fsum(
            (stored_value / stored_norm) * (query_value / query_norm)
            for stored_value, query_value in zip(stored, query, strict=True)
        )
        # Roundoff can exceed the mathematical cosine interval by a few ulps.
        return 1.0 - min(1.0, max(-1.0, cosine))

    return distance


def _source_values(metadata: dict[str, Any]) -> set[tuple[str, str]]:
    """Match Knowledge's historical Python str(), list intersection and missing semantics."""
    source = metadata.get("source_metadata")
    if isinstance(source, str):
        try:
            source = json.loads(source)
        except (ValueError, TypeError):
            return set()
    if not isinstance(source, dict):
        return set()
    return {
        (key, str(value))
        for key, actual in source.items()
        if isinstance(key, str) and actual is not None
        for value in (actual if isinstance(actual, list) else [actual])
    }


def _where(
    filters: dict[str, Any] | None = None, source_filter: dict[str, list[str]] | None = None
) -> tuple[str, list[Any]]:
    """Compile equality filters with bound values, independently of source metadata."""
    clauses: list[str] = []
    values: list[Any] = []
    if filters is not None and not isinstance(filters, dict):
        msg = "Unsupported metadata filter: expected an object"
        raise ValueError(msg)
    for key, value in (filters or {}).items():
        if not isinstance(key, str) or key.startswith("$") or not isinstance(value, (str, int, float, bool)):
            msg = "Unsupported metadata filter: only top-level scalar equality is supported"
            raise ValueError(msg)
        if isinstance(value, float) and not math.isfinite(value):
            msg = "Unsupported metadata filter: values must be finite"
            raise ValueError(msg)
        # json_each avoids interpreting a user key as SQL or as a JSON path.
        if key in {"job_id", "session_id"} and isinstance(value, str):
            clauses.append(f"c.{key} = ?")
            values.append(value)
        else:
            if isinstance(value, bool):
                value_type = "true" if value else "false"
            elif isinstance(value, str):
                value_type = "text"
            else:
                value_type = "number"
            clauses.append(
                "EXISTS (SELECT 1 FROM json_each(c.metadata) m WHERE m.key = ? AND m.value = ? "
                "AND (m.type = ? OR (? = 'number' AND m.type IN ('integer','real'))))"
            )
            values.extend([key, value, value_type, value_type])
    if source_filter is not None and not isinstance(source_filter, dict):
        msg = "Unsupported source metadata filter: expected an object"
        raise ValueError(msg)
    for key, expected in (source_filter or {}).items():
        if not isinstance(key, str) or not isinstance(expected, list) or not all(isinstance(v, str) for v in expected):
            msg = "Unsupported source metadata filter: expected lists of strings"
            raise ValueError(msg)
        if not expected:
            clauses.append("0")
            continue
        placeholders = ",".join("?" for _ in expected)
        clauses.append(
            "EXISTS (SELECT 1 FROM source_filter_values f WHERE f.document_id = c.id "  # noqa: S608 - placeholders only
            f"AND f.key = ? AND f.value_text IN ({placeholders}))"
        )
        values.extend([key, *expected])
    return " AND ".join(clauses) or "1", values


class SQLiteBackend(BaseVectorStoreBackend):
    """One durable local store for an immutable owner/KB/generation tuple."""

    backend_type = BackendType.SQLITE
    supports_source_metadata_filter = True

    def __init__(
        self,
        kb_name: str,
        kb_path: Path | None = None,
        backend_config: dict[str, Any] | None = None,
        embedding_function: Embeddings | None = None,
        user_id: UUID | str | None = None,
        *,
        storage_context: SQLiteStorageContext,
        create: bool = False,
    ) -> None:
        """Bind metric configuration and embeddings to a trusted immutable storage context."""
        super().__init__(kb_name, kb_path, backend_config, embedding_function, user_id)
        if kb_path is not None and Path(kb_path).absolute() != storage_context.database_path.parent:
            msg = "SQLite paths must come from immutable storage context"
            raise BackendConfigurationError(msg)
        unknown = set(self.backend_config) - {"metric", "model_fingerprint"}
        if unknown:
            msg = f"Unsupported SQLite configuration keys: {', '.join(sorted(unknown))}"
            raise BackendConfigurationError(msg)
        self.storage_context = storage_context
        self.kb_path = storage_context.database_path.parent
        self.metric = self.backend_config.get("metric", "l2")
        self.model_fingerprint = self.backend_config.get("model_fingerprint")
        if self.metric not in {"l2", "cosine", "ip"}:
            msg = "SQLite metric must be l2, cosine, or ip"
            raise BackendConfigurationError(msg)
        if self.model_fingerprint is not None and not isinstance(self.model_fingerprint, str):
            msg = "SQLite model_fingerprint must be a nonsecret string"
            raise BackendConfigurationError(msg)
        self._create = create
        self._ready = False

    @property
    def store_location(self) -> tuple[Any, ...]:
        """The database file, which holds only this generation of this KB."""
        return (self.storage_context.database_path,)

    @property
    def distance_metric(self) -> str:
        """The configured ``metric``, named the way the other backends name metrics."""
        return {"ip": "inner_product"}.get(self.metric, self.metric)

    async def _run(self, operation: Callable[..., _T], *args: Any, **kwargs: Any) -> _T:
        """Bound native work and do not release callers' guards while a cancelled write runs."""
        loop = asyncio.get_running_loop()
        executor = _worker_executor()
        reference = _LOOP_LIMITS.get(loop)
        limit = reference() if reference is not None else None
        if limit is None:
            limit = asyncio.Semaphore(_WORKERS)
            # A semaphore can retain its loop after contention. Neither side
            # of this process-wide lookup may keep a closed loop alive.
            _LOOP_LIMITS[loop] = weakref.ref(limit)
        async with limit:
            future = loop.run_in_executor(executor, partial(operation, *args, **kwargs))
            cancelled = False
            while True:
                try:
                    result = await asyncio.shield(future)
                    break
                except asyncio.CancelledError:
                    cancelled = True
                    if future.done():
                        # Retrieve failures to avoid abandoning an unobserved worker exception.
                        future.exception()
                        raise
                except Exception:
                    if cancelled:
                        raise asyncio.CancelledError from None
                    raise
            if cancelled:
                raise asyncio.CancelledError
            return result

    def _check_path(self, *, create: bool = False) -> Path:
        """Validate the store path and reject missing, symlinked or retired storage."""
        context = self.storage_context
        paths = [context.root]
        for segment in ("sqlite", str(context.owner_id), str(context.kb_id), str(context.generation)):
            paths.append(paths[-1] / segment)
        for path in paths:
            if path.is_symlink():
                msg = "SQLite storage paths must not contain a symlink"
                raise BackendConfigurationError(msg)
            if create:
                path.mkdir(mode=0o700, parents=path == context.root, exist_ok=True)
            if path.exists() and not path.is_dir():
                msg = "SQLite storage path is not a directory"
                raise BackendConfigurationError(msg)
        db_path = context.database_path
        for candidate in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
            if candidate.is_symlink():
                msg = "SQLite storage files must not be symlinks"
                raise BackendConfigurationError(msg)
        if create:
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(db_path, flags, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(descriptor)
        if not db_path.is_file():
            msg = "SQLite knowledge base storage is missing"
            raise FileNotFoundError(msg)
        return db_path

    @contextlib.contextmanager
    def _connect(self, *, initialize: bool = False, allow_deleted: bool = False) -> Iterator[Any]:
        # Lazy native imports keep unrelated backends and component discovery lightweight.
        """Open the private runtime connection and load only its pinned vector extension."""
        import apsw
        import sqlite_vec

        if sys.byteorder != "little":
            msg = "SQLite vector storage currently requires a little-endian platform"
            raise BackendConfigurationError(msg)
        if tuple(map(int, apsw.sqlitelibversion().split("."))) < (3, 51, 3):
            msg = "SQLite knowledge bases require APSW SQLite 3.51.3 or newer (WAL reset fix)"
            raise BackendConfigurationError(msg)
        path = self._check_path(create=initialize)
        connection = apsw.Connection(str(path), flags=apsw.SQLITE_OPEN_READWRITE | apsw.SQLITE_OPEN_NOFOLLOW)
        try:
            connection.set_busy_timeout(5000)
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA secure_delete=ON")
            # The extension path is exclusively package-owned, never a request/config value.
            extension_root = Path(sqlite_vec.__file__).resolve().parent
            extension = Path(sqlite_vec.loadable_path()).absolute()
            if extension.parent.resolve() != extension_root:
                msg = "sqlite-vec extension is outside its installed package"
                raise BackendConfigurationError(msg)
            connection.enable_load_extension(True)  # noqa: FBT003 - APSW API
            try:
                connection.load_extension(str(extension))
            finally:
                connection.enable_load_extension(False)  # noqa: FBT003 - APSW API
            if initialize:
                journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                if journal_mode != "wal":
                    msg = "SQLite knowledge base storage must support WAL journal mode"
                    raise BackendConfigurationError(msg)
                connection.execute("BEGIN IMMEDIATE")
                try:
                    connection.execute(_SCHEMA)
                    context = self.storage_context
                    connection.execute(
                        "INSERT OR IGNORE INTO store_header VALUES (1,?,?,?,?,?,?,?,?,?)",
                        [
                            _SCHEMA_VERSION,
                            str(uuid4()),
                            str(context.owner_id),
                            str(context.kb_id),
                            context.generation,
                            None,
                            self.metric,
                            self.model_fingerprint,
                            "active",
                        ],
                    )
                    self._header(connection)
                    connection.execute("COMMIT")
                except BaseException:
                    # FULL/IOERR can make SQLite roll back the transaction itself.
                    if not connection.get_autocommit():
                        connection.execute("ROLLBACK")
                    raise
            else:
                self._header(connection, allow_deleted=allow_deleted)
            yield connection
        finally:
            connection.close()

    def _header(self, connection: Any, *, allow_deleted: bool = False) -> dict[str, Any]:
        """Read and validate the store identity, metric and embedding schema."""
        try:
            rows = list(
                connection.execute(
                    f"SELECT {','.join(_HEADER_KEYS)} FROM store_header WHERE singleton=1"  # noqa: S608 - constant columns
                )
            )
        except Exception as exc:
            msg = "SQLite store header is missing or invalid"
            raise BackendConfigurationError(msg) from exc
        if len(rows) != 1:
            msg = "SQLite store header is missing or invalid"
            raise BackendConfigurationError(msg)
        header = dict(zip(_HEADER_KEYS, rows[0], strict=True))
        context = self.storage_context
        expected = {
            "schema_version": _SCHEMA_VERSION,
            "owner_id": str(context.owner_id),
            "kb_id": str(context.kb_id),
            "generation": context.generation,
        }
        # Erasure needs the immutable ownership identity, including for an
        # unpublished migration target whose embedding config was never routed.
        if not allow_deleted:
            expected["metric"] = self.metric
            if self.model_fingerprint is not None:
                expected["model_fingerprint"] = self.model_fingerprint
        for key, value in expected.items():
            if header[key] != value:
                msg = f"SQLite store {key} does not match its configured storage context"
                raise BackendConfigurationError(msg)
        if not allow_deleted and header["lifecycle"] != "active":
            msg = "SQLite storage generation has been deleted"
            raise BackendConfigurationError(msg)
        return header

    def _initialize(self) -> None:
        """Create the database schema and persist its immutable storage header."""
        with self._connect(initialize=self._create):
            pass

    async def ensure_ready(self) -> None:
        """Validate or explicitly initialize the store in a worker thread."""
        if not self._ready:
            await self._run(self._initialize)
            self._ready = True
            self._create = False

    def _build_vector_store(self) -> VectorStore:
        """Expose the LangChain adapter for this SQLite backend."""
        return _SQLiteVectorStore(self)

    def _upsert(self, ids: list[str], docs: list[IngestedDocument]) -> None:
        """Atomically persist document text, metadata and already validated vectors."""
        if len(ids) != len(docs) or len(set(ids)) != len(ids):
            msg = "SQLite document IDs must be unique within a batch"
            raise ValueError(msg)
        prepared = []
        for document_id, doc in zip(ids, docs, strict=True):
            if not isinstance(document_id, str) or not document_id:
                msg = "SQLite document IDs must be nonempty strings"
                raise ValueError(msg)
            if not isinstance(doc.metadata, dict) or not isinstance(doc.content, str):
                msg = "SQLite documents require text content and object metadata"
                raise TypeError(msg)
            blob, dimension = _vector_blob(doc.embedding, metric=self.metric)
            metadata = _metadata_json(doc.metadata)
            job_id = doc.metadata.get("job_id")
            session_id = doc.metadata.get("session_id")
            prepared.append(
                (
                    document_id,
                    doc.content,
                    metadata,
                    blob,
                    dimension,
                    job_id if isinstance(job_id, str) else None,
                    session_id if isinstance(session_id, str) else None,
                    int(_native_distance_safe(blob)),
                    _source_values(doc.metadata),
                )
            )
        if not prepared:
            return
        dimensions = {row[4] for row in prepared}
        if len(dimensions) != 1:
            msg = "SQLite batch embedding dimension is inconsistent"
            raise BackendConfigurationError(msg)
        dimension = next(iter(dimensions))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                header = self._header(connection)
                if header["dimension"] is not None and header["dimension"] != dimension:
                    msg = "SQLite embedding dimension does not match the stored collection"
                    raise BackendConfigurationError(msg)
                connection.execute("UPDATE store_header SET dimension=? WHERE singleton=1", (dimension,))
                for row in prepared:
                    connection.execute(
                        "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                        "content=excluded.content,metadata=excluded.metadata,vector=excluded.vector,"
                        "dimension=excluded.dimension,job_id=excluded.job_id,session_id=excluded.session_id,"
                        "native_distance_safe=excluded.native_distance_safe",
                        row[:8],
                    )
                    connection.execute("DELETE FROM source_filter_values WHERE document_id=?", (row[0],))
                    connection.executemany(
                        "INSERT INTO source_filter_values VALUES (?,?,?)",
                        [(row[0], key, value) for key, value in sorted(row[8])],
                    )
                connection.execute("COMMIT")
            except BaseException:
                # FULL/IOERR can make SQLite roll back the transaction itself.
                if not connection.get_autocommit():
                    connection.execute("ROLLBACK")
                raise

    async def _write_embedded(self, ids: list[str], docs: list[IngestedDocument]) -> None:
        """Offload supplied-vector writes without calling an embedding provider."""
        await self.ensure_ready()
        await self._run(self._upsert, ids, docs)

    async def _add_documents(self, docs: list[Document], ids: list[str] | None = None) -> list[str]:
        """Embed document batches and persist them with stable IDs."""
        if not docs:
            return []
        if self.embedding_function is None:
            msg = "SQLite ingestion requires an embedding function"
            raise BackendConfigurationError(msg)
        if ids is not None and len(ids) != len(docs):
            msg = "SQLite IDs and documents must have the same length"
            raise ValueError(msg)
        ids = ids if ids is not None else [doc.id or str(uuid4()) for doc in docs]
        vectors = await self.embedding_function.aembed_documents([doc.page_content for doc in docs])
        if len(vectors) != len(docs):
            msg = "Embedding provider returned an incorrect number of vectors"
            raise BackendConfigurationError(msg)
        embedded = [
            IngestedDocument(doc.page_content, doc.metadata, vector, id=document_id)
            for doc, vector, document_id in zip(docs, vectors, ids, strict=True)
        ]
        await self._write_embedded(ids, embedded)
        return ids

    def _search(
        self, vector: list[float], k: int, filters: dict[str, Any] | None, source_filter: dict[str, list[str]] | None
    ) -> list[tuple[Document, float]]:
        """Find exact nearest neighbors with bound metadata filters and stable result ordering."""
        blob, dimension = _vector_blob(vector, metric=self.metric)
        where, parameters = _where(filters, source_filter)
        with self._connect() as connection:
            header = self._header(connection)
            if header["dimension"] is None:
                return []
            if header["dimension"] != dimension:
                msg = "SQLite query embedding dimension does not match the stored collection"
                raise BackendConfigurationError(msg)
            if self.metric == "ip":
                import numpy as np

                query: NDArray[np.float64] = np.frombuffer(blob, dtype="<f4").astype(np.float64)
                cursor = iter(
                    connection.execute(
                        f"SELECT c.id,c.content,c.metadata,c.vector FROM chunks c WHERE {where}",  # noqa: S608 - bound filters
                        parameters,
                    )
                )
                candidates: list[tuple[float, str, str, str]] = []
                while True:
                    batch = []
                    for _ in range(256):
                        row = next(cursor, None)
                        if row is None:
                            break
                        batch.append(row)
                    if not batch:
                        break
                    matrix = np.stack([np.frombuffer(row[3], dtype="<f4") for row in batch]).astype(np.float64)
                    distances = 1.0 - matrix @ query
                    candidates = heapq.nsmallest(
                        k,
                        candidates
                        + [
                            (float(distance), row[0], row[1], row[2])
                            for row, distance in zip(batch, distances, strict=True)
                        ],
                    )
                return [
                    (Document(id=row[1], page_content=row[2], metadata=json.loads(row[3])), row[0])
                    for row in candidates
                ]
            connection.create_scalar_function(
                "kb_stable_distance", _stable_distance_function(blob, metric=self.metric), 1, deterministic=True
            )
            native_distance = (
                "vec_distance_L2(c.vector, ?)" if self.metric == "l2" else "vec_distance_cosine(c.vector, ?)"
            )
            # SQLite CASE is lazy: extreme pairs never enter the unsafe native
            # function. Both paths participate in the same filtered top-k sort.
            distance = (
                f"CASE WHEN ? AND c.native_distance_safe THEN {native_distance} ELSE kb_stable_distance(c.vector) END"
            )
            rows = connection.execute(
                f"SELECT c.id,c.content,c.metadata,{distance} distance FROM chunks c "  # noqa: S608 - constant distance, bound filters
                f"WHERE {where} ORDER BY distance,c.id LIMIT ?",
                [int(_native_distance_safe(blob)), blob, *parameters, k],
            )
            results = []
            for document_id, content, metadata, raw_distance in rows:
                if raw_distance is None or not math.isfinite(raw_distance):
                    msg = "SQLite vector distance is nonfinite"
                    raise BackendConfigurationError(msg)
                score = raw_distance * raw_distance if self.metric == "l2" else raw_distance
                results.append((Document(id=document_id, page_content=content, metadata=json.loads(metadata)), score))
            return results

    async def similarity_search(
        self,
        query: str,
        k: int,
        *,
        filter: dict[str, Any] | None = None,  # noqa: A002
        with_scores: bool = False,
        source_filter: dict[str, list[str]] | None = None,
    ) -> list[tuple[Document, float]]:
        """Embed a query and search the validated store with optional source filters."""
        if type(k) is not int or k < 0:
            msg = "SQLite search k must be a nonnegative integer"
            raise ValueError(msg)
        _where(filter, source_filter)
        if k == 0:
            return []
        if self.embedding_function is None:
            msg = "SQLite search requires an embedding function"
            raise BackendConfigurationError(msg)
        await self.ensure_ready()
        vector = await self.embedding_function.aembed_query(query)
        result = await self._run(self._search, vector, k, filter, source_filter)
        return result if with_scores else [(document, 0.0) for document, _ in result]

    def _count(self) -> int:
        """Count durable documents using a checked runtime connection."""
        with self._connect() as connection:
            return connection.execute("SELECT count(*) FROM chunks").fetchone()[0]

    async def count(self) -> int:
        """Offload the document count so SQLite cannot block the event loop."""
        await self.ensure_ready()
        return await self._run(self._count)

    def _read_only_count(self) -> int | None:
        """Inspect existing storage without initialization or a writable connection."""
        import apsw

        try:
            path = self._check_path()
        except FileNotFoundError:
            return None
        with contextlib.closing(
            apsw.Connection(str(path), flags=apsw.SQLITE_OPEN_READONLY | apsw.SQLITE_OPEN_NOFOLLOW)
        ) as connection:
            # Use the private runtime's WAL reader so committed, uncheckpointed
            # chunks count too. Validate identity before trusting the stored count.
            self._header(connection)
            return connection.execute("SELECT count(*) FROM chunks").fetchone()[0]

    async def read_only_count(self) -> int | None:
        """Count existing chunks without invoking the store's initialization path."""
        return await self._run(self._read_only_count)

    def _read_batch(
        self, after: str | None, batch_size: int, *, include_embeddings: bool, max_batch_bytes: int
    ) -> list[IngestedDocument]:
        # Keyset pagination does not skip rows merely because an earlier row is deleted.
        # Strict cross-batch snapshot consistency requires the caller's whole-KB guard.
        """Read a bounded batch after the supplied stable document cursor."""
        with self._connect() as connection:
            where, parameters = ("id > ?", [after]) if after is not None else ("1", [])
            vector_column = "vector" if include_embeddings else "NULL"
            rows = connection.execute(
                f"SELECT id,content,metadata,{vector_column},dimension FROM chunks WHERE {where} ORDER BY id LIMIT ?",  # noqa: S608 - constant clauses
                [*parameters, batch_size],
            )
            result: list[IngestedDocument] = []
            batch_bytes = 0
            for document_id, content, metadata, blob, dimension in rows:
                row_bytes = sum(len(value.encode("utf-8")) for value in (document_id, content, metadata))
                row_bytes += len(blob) if blob is not None else 0
                if row_bytes > max_batch_bytes:
                    msg = "SQLite stored document exceeds the iteration byte limit"
                    raise BackendConfigurationError(msg)
                if result and batch_bytes + row_bytes > max_batch_bytes:
                    break
                batch_bytes += row_bytes
                vector = list(struct.unpack(f"<{dimension}f", blob)) if blob is not None else None
                if vector is not None:
                    _vector_blob(vector, metric=self.metric)
                result.append(IngestedDocument(content, json.loads(metadata), vector, id=document_id))
            return result

    async def iter_documents(
        self, *, batch_size: int = 5000, include_embeddings: bool = False, max_batch_bytes: int = 16 * 1024 * 1024
    ) -> AsyncIterator[list[IngestedDocument]]:
        """Stream durable documents in bounded batches with optional stored embeddings."""
        if type(batch_size) is not int or batch_size < 1:
            msg = "SQLite batch_size must be positive"
            raise ValueError(msg)
        if type(max_batch_bytes) is not int or max_batch_bytes < 1:
            msg = "SQLite max_batch_bytes must be positive"
            raise ValueError(msg)
        await self.ensure_ready()
        after = None
        while batch := await self._run(
            self._read_batch,
            after,
            batch_size,
            include_embeddings=include_embeddings,
            max_batch_bytes=max_batch_bytes,
        ):
            yield batch
            after = batch[-1].id

    def _delete(self, *, ids: list[str] | None = None, where: dict[str, Any] | None = None) -> None:
        """Remove matching documents using bound metadata predicates."""
        if ids is None and not where:
            msg = "SQLite deletion requires IDs or a nonempty filter"
            raise ValueError(msg)
        clause, parameters = _where(where)
        if ids is not None:
            if not ids:
                return
            if not all(isinstance(document_id, str) for document_id in ids):
                msg = "SQLite deletion IDs must be strings"
                raise ValueError(msg)
            clause += f" AND c.id IN ({','.join('?' for _ in ids)})"
            parameters.extend(ids)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._header(connection)
                connection.execute(
                    f"DELETE FROM chunks WHERE id IN (SELECT c.id FROM chunks c WHERE {clause})",  # noqa: S608 - bound filters
                    parameters,
                )
                manifest_row = connection.execute(
                    "SELECT manifest FROM migration_manifest WHERE singleton=1"
                ).fetchone()
                if manifest_row is not None:
                    manifest = json.loads(manifest_row[0])
                    if manifest.get("status") == "complete":
                        manifest.setdefault("imported_count", manifest["count"])
                        manifest["count"] = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
                        connection.execute(
                            "UPDATE migration_manifest SET manifest=? WHERE singleton=1", (_json(manifest),)
                        )
                connection.execute("COMMIT")
            except BaseException:
                # FULL/IOERR can make SQLite roll back the transaction itself.
                if not connection.get_autocommit():
                    connection.execute("ROLLBACK")
                raise

    async def delete_by(self, where: dict[str, Any]) -> None:
        """Offload filtered deletion while preserving the collection schema."""
        await self.ensure_ready()
        await self._run(self._delete, where=where)

    async def delete_collection(self) -> None:
        """Tombstone before removing rows. File removal belongs to guarded lifecycle cleanup."""

        def tombstone() -> None:
            """Erase chunk content and persist the generation deletion tombstone atomically."""
            with self._connect(allow_deleted=True) as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    header = self._header(connection, allow_deleted=True)
                    if header["lifecycle"] != "deleted":
                        connection.execute("DELETE FROM chunks")
                        connection.execute("UPDATE store_header SET lifecycle='deleted' WHERE singleton=1")
                    connection.execute("COMMIT")
                except BaseException:
                    # FULL/IOERR can make SQLite roll back the transaction itself.
                    if not connection.get_autocommit():
                        connection.execute("ROLLBACK")
                    raise

                # Retain the generation tombstone, but reclaim pages containing
                # deleted text and truncate the WAL before acknowledging deletion.
                connection.execute("VACUUM")
                busy, _log, _checkpointed = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                if busy:
                    msg = "SQLite deletion checkpoint is blocked by another connection"
                    raise BackendConfigurationError(msg)

        await self._run(tombstone)

    async def storage_size_bytes(self) -> int:
        """Measure the database and its WAL and shared-memory files."""
        await self.ensure_ready()

        def size() -> int:
            """Sum the current database, write-ahead log and shared-memory file sizes."""
            path = self._check_path()
            total = 0
            for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
                with contextlib.suppress(FileNotFoundError):
                    total += candidate.stat().st_size
            return total

        return await self._run(size)

    async def inspect_store(self) -> dict[str, Any]:
        """Read storage header metadata without creating a missing database."""
        await self.ensure_ready()

        def inspect() -> dict[str, Any]:
            """Read the validated storage identity and lifecycle header."""
            with self._connect() as connection:
                return self._header(connection)

        return await self._run(inspect)

    async def integrity_check(self) -> None:
        """Verify SQLite integrity and the persisted collection schema."""
        await self.ensure_ready()

        def check() -> None:
            """Require SQLite integrity and foreign-key checks to pass."""
            with self._connect() as connection:
                if list(connection.execute("PRAGMA integrity_check")) != [("ok",)] or list(
                    connection.execute("PRAGMA foreign_key_check")
                ):
                    msg = "SQLite knowledge base integrity verification failed"
                    raise BackendConfigurationError(msg)
                dimension = self._header(connection)["dimension"]
                invalid = connection.execute(
                    "SELECT count(*) FROM chunks WHERE dimension IS NOT ? OR length(vector) != dimension*4",
                    (dimension,),
                ).fetchone()[0]
                if invalid:
                    msg = "SQLite knowledge base vector dimensions are inconsistent"
                    raise BackendConfigurationError(msg)

        await self._run(check)

    async def set_migration_dimension(self, dimension: int | None) -> None:
        """Preserve a known source dimension even when an exported store is empty.

        Only a staged generation with an importing manifest may establish it.
        The caller must hold the same exclusive gate as the complete import.
        """
        if dimension is None:
            return
        if type(dimension) is not int or not 1 <= dimension <= _MAX_MIGRATION_DIMENSIONS:
            msg = "Migration dimension must be an integer between 1 and 32768"
            raise BackendConfigurationError(msg)
        await self.ensure_ready()

        def set_dimension() -> None:
            """Persist the embedding dimension or reject a conflicting existing dimension."""
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    header = self._header(connection)
                    if header["dimension"] is not None:
                        if header["dimension"] != dimension:
                            msg = "Migration dimension conflicts with the stored collection"
                            raise BackendConfigurationError(msg)
                    else:
                        row = connection.execute("SELECT manifest FROM migration_manifest WHERE singleton=1").fetchone()
                        if row is None or json.loads(row[0]).get("status") != "importing":
                            msg = "Migration dimension requires an importing manifest"
                            raise BackendConfigurationError(msg)
                        connection.execute("UPDATE store_header SET dimension=? WHERE singleton=1", (dimension,))
                    connection.execute("COMMIT")
                except BaseException:
                    # FULL/IOERR can make SQLite roll back the transaction itself.
                    if not connection.get_autocommit():
                        connection.execute("ROLLBACK")
                    raise

        await self._run(set_dimension)

    async def read_migration_manifest(self) -> dict[str, Any] | None:
        """Read the target's migration evidence without mutating the store."""
        await self.ensure_ready()

        def read() -> dict[str, Any] | None:
            """Read the durable migration manifest when one has been recorded."""
            with self._connect() as connection:
                row = connection.execute("SELECT manifest FROM migration_manifest WHERE singleton=1").fetchone()
                return json.loads(row[0]) if row else None

        return await self._run(read)

    async def save_migration_manifest(self, manifest: dict[str, Any]) -> None:
        """Persist migration evidence for resumable target verification."""
        await self.ensure_ready()
        if not isinstance(manifest, dict):
            msg = "SQLite migration manifest must be an object"
            raise TypeError(msg)
        encoded = _json(manifest)

        def save() -> None:
            """Persist the encoded migration manifest in a single transaction."""
            with self._connect() as connection, connection:
                connection.execute(
                    "INSERT INTO migration_manifest VALUES(1,?) "
                    "ON CONFLICT(singleton) DO UPDATE SET manifest=excluded.manifest",
                    (encoded,),
                )

        await self._run(save)

    async def finalize_migration(self, manifest: dict[str, Any]) -> None:
        """Persist caller-verified completion, checkpoint and fsync before routing can change."""
        await self.save_migration_manifest(manifest)

        def flush() -> None:
            """Checkpoint migration writes and synchronize the target files."""
            with self._connect() as connection:
                busy, _log, _checkpointed = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                if busy:
                    msg = "SQLite migration checkpoint is blocked by another connection"
                    raise BackendConfigurationError(msg)
            path = self._check_path()
            with path.open("r+b") as file:
                os.fsync(file.fileno())
            if os.name != "nt":
                descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)

        await self._run(flush)

    async def test_connection(self) -> TestConnectionResult:
        """Verify local runtime availability without requiring provider credentials."""
        try:
            await self.ensure_ready()
            await self.integrity_check()
        except Exception as exc:  # noqa: BLE001 - connection test result intentionally reports failure
            return TestConnectionResult(ok=False, message=str(exc), details={"type": type(exc).__name__})
        return TestConnectionResult(ok=True, message="SQLite knowledge base storage is available")


class _SQLiteVectorStore(VectorStore):
    """LangChain facade. Async operations retain worker cancellation guarantees."""

    def __init__(self, backend: SQLiteBackend) -> None:
        """Adapt the backend to the LangChain vector-store interface."""
        self._backend = backend

    @property
    def embeddings(self) -> Embeddings | None:
        """Expose the embedding function configured on the backing store."""
        return self._backend.embedding_function

    @classmethod
    def from_texts(
        cls, texts: list[str], embedding: Embeddings, metadatas: list[dict[str, Any]] | None = None, **kwargs: Any
    ) -> _SQLiteVectorStore:
        """Reject implicit construction without the required immutable storage context."""
        msg = "Construct SQLite stores through SQLiteBackend with trusted storage context"
        raise NotImplementedError(msg)

    def similarity_search(self, query: str, k: int = 4, **kwargs: Any) -> list[Document]:
        """Reject synchronous search in favor of the asynchronous SQLite API."""
        msg = "Use SQLiteVectorStore async search methods"
        raise NotImplementedError(msg)

    async def aadd_documents(self, documents: list[Document], **kwargs: Any) -> list[str]:
        """Delegate document embedding and persistence to the SQLite backend."""
        return await self._backend._add_documents(documents, ids=kwargs.get("ids"))  # noqa: SLF001 - companion facade

    async def aadd_texts(
        self,
        texts: Iterable[str],
        metadatas: list[dict[str, Any]] | None = None,
        *,
        ids: list[str] | None = None,
        **kwargs: Any,  # noqa: ARG002 - LangChain interface
    ) -> list[str]:
        """Convert texts and metadata into documents before asynchronous ingestion."""
        materialized = list(texts)
        if metadatas is not None and len(metadatas) != len(materialized):
            msg = "SQLite text and metadata counts must match"
            raise ValueError(msg)
        documents = [
            Document(page_content=text, metadata=metadatas[i] if metadatas else {})
            for i, text in enumerate(materialized)
        ]
        return await self._backend._add_documents(documents, ids=ids)  # noqa: SLF001 - companion facade

    async def asimilarity_search(self, query: str, k: int = 4, **kwargs: Any) -> list[Document]:
        """Return matching documents from the backend's asynchronous query."""
        return [doc for doc, _ in await self.asimilarity_search_with_score(query, k=k, **kwargs)]

    async def asimilarity_search_with_score(
        self, query: str, k: int = 4, **kwargs: Any
    ) -> list[tuple[Document, float]]:
        """Return matching documents with the backend's metric scores."""
        return await self._backend.similarity_search(
            query, k, filter=kwargs.get("filter"), source_filter=kwargs.get("source_filter"), with_scores=True
        )

    async def adelete(self, ids: list[str] | None = None, **kwargs: Any) -> bool:
        """Delete the requested document IDs from the SQLite collection."""
        await self._backend.ensure_ready()
        await self._backend._run(self._backend._delete, ids=ids, where=kwargs.get("where"))  # noqa: SLF001 - companion facade
        return True

    async def aget_by_ids(self, ids: list[str]) -> list[Document]:
        """Retrieve stored documents for the requested stable IDs."""
        await self._backend.ensure_ready()
        if not ids:
            return []

        def get() -> list[Document]:
            """Fetch requested documents once each while preserving request order."""
            with self._backend._connect() as connection:  # noqa: SLF001 - companion facade
                documents = {}
                for document_id in dict.fromkeys(ids):
                    row = connection.execute(
                        "SELECT content,metadata FROM chunks WHERE id=?", (document_id,)
                    ).fetchone()
                    if row:
                        documents[document_id] = Document(
                            id=document_id, page_content=row[0], metadata=json.loads(row[1])
                        )
                return list(documents.values())

        return await self._backend._run(get)  # noqa: SLF001 - companion facade
