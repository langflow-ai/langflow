"""Unit tests for the pgVector (``PostgresBackend``) knowledge-base backend.

These exercise the backend's SQL construction, per-collection table layout and
lifecycle/error handling without a database. The connection is a fake, but every
statement the backend builds is compiled with SQLAlchemy's real PostgreSQL
dialect, so the SQL asserted here is the SQL production emits.

The live round-trip against a real pgvector database lives in
``src/backend/tests/unit/base/knowledge_bases/test_postgres_backend.py`` and is
opt-in via ``LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1``.
"""

from __future__ import annotations

import sys
import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding, Embeddings
from lfx.base.knowledge_bases.backends import BackendType, PostgresBackend, create_backend
from lfx.base.knowledge_bases.backends.base import BackendConfigurationError
from lfx.base.knowledge_bases.backends.postgres import (
    _HNSW_MAX_DIM,
    MISSING_CREATE_PRIVILEGE_DETAILS_TYPE,
    MISSING_CREATE_PRIVILEGE_MESSAGE,
    MISSING_EXTENSION_DETAILS_TYPE,
    MISSING_EXTENSION_MESSAGE,
    _coerce_embedding,
    _count_sql,
    _delete_by_sql,
    _dimension_mismatch_message,
    _drop_table_sql,
    _iter_documents_sql,
    _normalize_driver,
    _parse_pgvector_version,
    _parse_vector_dim,
    _PostgresVectorStore,
    _translate_dimension_error,
    _validate_table_name,
    postgres_env_configured,
    read_connection_string_from_env,
    resolve_default_kb_backend,
)

if TYPE_CHECKING:
    from pathlib import Path

    from lfx.base.knowledge_bases.backends.base import IngestedDocument

# A syntactically valid collection table name (``lf_`` + 24 lowercase hex).
_VALID_TABLE = "lf_0123456789abcdef01234567"
_CONNECTION_STRING = "postgresql://user:pass@localhost:5432/db"  # pragma: allowlist secret


def _render(statement: Any) -> str:
    """Render a statement the way PostgreSQL will receive it.

    Literal SQL keeps its ``:name`` bind markers so assertions read like the
    source; constructed statements are compiled with the real PostgreSQL dialect
    so the ON CONFLICT / ``<=>`` syntax under test is genuinely produced.
    """
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.sql.elements import TextClause

    if isinstance(statement, TextClause):
        return str(statement)
    return str(statement.compile(dialect=postgresql.dialect()))


class _DatabaseError(RuntimeError):
    """Stands in for a driver-level failure."""


class _FakeResult:
    def __init__(self, rows: tuple[Any, ...]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _FakeStream:
    def __init__(self, rows: tuple[Any, ...]) -> None:
        self._rows = rows

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for row in self._rows:
            yield row


class _FakeConn:
    """Async connection stub that answers the catalog probes postgres.py issues.

    ``raise_on`` makes the connection fail once the rendered SQL contains that
    fragment, which is how the "database went away" branches are reached.
    """

    def __init__(
        self,
        *,
        ext_version: str | None = "0.7.0",
        server_version: str | None = "16.1",
        table_exists: bool = True,
        row_count: int = 0,
        existing_dim: int | None = None,
        select_rows: tuple[Any, ...] = (),
        stream_rows: tuple[Any, ...] = (),
        storage_size: int = 0,
        can_create: bool | None = True,
        raise_on: str | None = None,
    ) -> None:
        self._ext_version = ext_version
        self._server_version = server_version
        self._table_exists = table_exists
        self._row_count = row_count
        self._existing_dim = existing_dim
        self._select_rows = select_rows
        self._stream_rows = stream_rows
        self._storage_size = storage_size
        self._can_create = can_create
        self._raise_on = raise_on
        self.statements: list[str] = []

    def _record(self, statement: Any) -> str:
        sql = _render(statement)
        self.statements.append(sql)
        if self._raise_on is not None and self._raise_on in sql:
            raise _DatabaseError(sql)
        return sql

    async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeResult:  # noqa: ARG002
        self._record(statement)
        return _FakeResult(self._select_rows)

    async def scalar(self, statement: Any, params: dict[str, Any] | None = None) -> Any:  # noqa: ARG002
        sql = self._record(statement)
        if "pg_total_relation_size" in sql:
            return self._storage_size
        # ``format_type`` before ``to_regclass``: the embedding-dim probe now
        # resolves its relation via ``to_regclass`` too, so the more specific
        # fragment must win.
        if "format_type" in sql:
            return None if self._existing_dim is None else f"vector({self._existing_dim})"
        if "to_regclass" in sql:
            return _VALID_TABLE if self._table_exists else None
        if "has_schema_privilege" in sql:
            return self._can_create
        if "extversion" in sql:
            return self._ext_version
        if "server_version" in sql:
            return self._server_version
        if "count(*)" in sql:
            return self._row_count
        return None

    async def stream(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeStream:  # noqa: ARG002
        self._record(statement)
        return _FakeStream(self._stream_rows)


class _FakeAcm:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _FakeEngine:
    """Stub engine whose ``connect``/``begin`` both yield the same fake conn."""

    def __init__(self, conn: _FakeConn, *, dispose_error: Exception | None = None) -> None:
        self._conn = conn
        self._dispose_error = dispose_error
        self.disposed = False

    def connect(self) -> _FakeAcm:
        return _FakeAcm(self._conn)

    def begin(self) -> _FakeAcm:
        return _FakeAcm(self._conn)

    async def dispose(self) -> None:
        if self._dispose_error is not None:
            raise self._dispose_error
        self.disposed = True


class _CountingEmbeddings(Embeddings):
    """Returns a caller-chosen number of vectors, to drive the mismatch guard."""

    def __init__(self, *, vectors: list[list[float]]) -> None:
        self._vectors = vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:  # noqa: ARG002
        return self._vectors

    def embed_query(self, text: str) -> list[float]:  # noqa: ARG002
        return self._vectors[0] if self._vectors else []


@pytest.fixture
def pgvector_env(monkeypatch: pytest.MonkeyPatch) -> str:
    """Provision pgVector the way a deployment does: one environment variable."""
    monkeypatch.setenv("PGVECTOR_CONNECTION_STRING", _CONNECTION_STRING)
    return _CONNECTION_STRING


@pytest.fixture
def fake_embeddings() -> DeterministicFakeEmbedding:
    return DeterministicFakeEmbedding(size=8)


@pytest.fixture
def make_backend(tmp_path: Path, pgvector_env: str):  # noqa: ARG001 — env must be set before ensure_ready
    """Build a PostgresBackend wired to a fake engine, ready for DB calls."""

    def _make(conn: _FakeConn | None = None, *, embeddings: Embeddings | None = None, kb_name: str = "kb"):
        backend = create_backend(
            "postgres",
            kb_name=kb_name,
            kb_path=tmp_path,
            backend_config={},
            embedding_function=embeddings,
            user_id=uuid.uuid4(),
        )
        engine = _FakeEngine(conn) if conn is not None else None
        if engine is not None:
            backend._pg_engine = engine
        return backend

    return _make


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------


class TestDriverNormalization:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("postgresql+psycopg://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
            ("postgresql+psycopg2://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
            ("postgresql://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
            ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ],
    )
    def test_normalize_forces_psycopg3(self, url: str, expected: str) -> None:
        assert _normalize_driver(url) == expected

    def test_unrecognized_scheme_is_left_alone(self) -> None:
        assert _normalize_driver("mysql://u:p@h/db") == "mysql://u:p@h/db"


class TestEnvDetection:
    def test_configured_when_env_present(self, pgvector_env: str) -> None:
        assert postgres_env_configured() is True
        assert read_connection_string_from_env() == pgvector_env
        assert resolve_default_kb_backend() == BackendType.POSTGRES.value

    def test_not_configured_when_env_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
        assert postgres_env_configured() is False
        assert read_connection_string_from_env() is None
        assert resolve_default_kb_backend() == BackendType.CHROMA.value

    def test_empty_env_is_treated_as_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PGVECTOR_CONNECTION_STRING", "")
        assert read_connection_string_from_env() is None


class TestSqlBuilders:
    # The expected-SQL literals below interpolate the fixed ``_VALID_TABLE``
    # constant, which is exactly the shape ``_validate_table_name`` enforces.
    def test_queries_target_the_per_collection_table(self) -> None:
        assert _count_sql(_VALID_TABLE) == f"SELECT count(*) FROM {_VALID_TABLE}"  # noqa: S608
        # ``where`` stays a bound parameter; only the validated table name is interpolated.
        delete_sql = _delete_by_sql(_VALID_TABLE)
        assert delete_sql.startswith(f"DELETE FROM {_VALID_TABLE} ")  # noqa: S608
        assert ":where" in delete_sql
        assert _drop_table_sql(_VALID_TABLE) == f'DROP TABLE IF EXISTS "{_VALID_TABLE}"'

    def test_iter_sql_selects_embedding_only_when_requested(self) -> None:
        assert _iter_documents_sql(_VALID_TABLE, include_embeddings=False) == (
            f"SELECT document, cmetadata FROM {_VALID_TABLE}"  # noqa: S608
        )
        assert _iter_documents_sql(_VALID_TABLE, include_embeddings=True) == (
            f"SELECT document, cmetadata, embedding FROM {_VALID_TABLE}"  # noqa: S608
        )

    @pytest.mark.parametrize(
        "bad_name",
        [
            "langchain_pg_embedding",  # not an lf_ hash
            "lf_short",
            "lf_0123456789abcdef01234567; DROP TABLE users",  # injection attempt
            "lf_0123456789ABCDEF01234567",  # uppercase hex rejected
            "LF_0123456789abcdef01234567",
            "",
        ],
    )
    def test_rejects_unexpected_table_name(self, bad_name: str) -> None:
        for builder in (_validate_table_name, _count_sql, _delete_by_sql, _drop_table_sql):
            with pytest.raises(ValueError, match="collection table name"):
                builder(bad_name)
        with pytest.raises(ValueError, match="collection table name"):
            _iter_documents_sql(bad_name, include_embeddings=False)

    def test_accepts_valid_table_name(self) -> None:
        assert _validate_table_name(_VALID_TABLE) == _VALID_TABLE


class TestParseVectorDim:
    def test_parses_dimension(self) -> None:
        assert _parse_vector_dim("vector(1536)") == 1536

    @pytest.mark.parametrize("type_str", ["vector", None, "text", ""])
    def test_dimensionless_and_garbage(self, type_str: str | None) -> None:
        assert _parse_vector_dim(type_str) is None


class TestCoerceEmbedding:
    def test_list_and_tuple_passthrough(self) -> None:
        assert _coerce_embedding([0.1, 0.2]) == [0.1, 0.2]
        assert _coerce_embedding((1, 2)) == [1.0, 2.0]

    def test_pgvector_string_repr(self) -> None:
        assert _coerce_embedding("[0.1, 0.2, 0.3]") == [0.1, 0.2, 0.3]

    @pytest.mark.parametrize("raw", [None, "not-a-vector", '{"a": 1}'])
    def test_none_and_garbage(self, raw: Any) -> None:
        assert _coerce_embedding(raw) is None


# --------------------------------------------------------------------------
# Collection identity + configuration
# --------------------------------------------------------------------------


class TestCollectionIdentity:
    def test_backend_type_and_collection_is_scoped_to_owner(self, tmp_path: Path) -> None:
        backend = create_backend("postgres", kb_name="my_kb", kb_path=tmp_path, backend_config={}, user_id=uuid.uuid4())
        assert isinstance(backend, PostgresBackend)
        assert backend.backend_type is BackendType.POSTGRES
        assert backend.collection_name.startswith("lf_")
        assert backend.collection_name != "my_kb"
        assert backend.table_name == backend.collection_name

    def test_same_kb_name_isolated_between_owners(self, tmp_path: Path) -> None:
        kwargs = {"kb_name": "shared", "kb_path": tmp_path, "backend_config": {}}
        first = create_backend("postgres", user_id=uuid.uuid4(), **kwargs)
        second = create_backend("postgres", user_id=uuid.uuid4(), **kwargs)
        assert first.collection_name != second.collection_name

    def test_collection_name_is_stable_for_the_same_owner(self, tmp_path: Path) -> None:
        owner = uuid.uuid4()
        kwargs = {"kb_name": "stable", "kb_path": tmp_path, "backend_config": {}}
        first = create_backend("postgres", user_id=owner, **kwargs)
        second = create_backend("postgres", user_id=owner, **kwargs)
        assert first.collection_name == second.collection_name

    def test_collection_requires_valid_owner(self, tmp_path: Path) -> None:
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={})
        with pytest.raises(ValueError, match="valid user_id"):
            _ = backend.collection_name

    def test_cosine_distance_score_is_normalized_to_higher_is_better(self, tmp_path: Path) -> None:
        backend = create_backend("postgres", kb_name="scores", kb_path=tmp_path, backend_config={})
        assert backend.normalize_score(0.25) == -0.25


class TestSecretResolution:
    @pytest.mark.usefixtures("pgvector_env")
    async def test_env_connection_string_skips_variable_service(self, tmp_path: Path) -> None:
        # pgVector is env-driven: when the env var is set, resolution must NOT
        # query the variable service (doing so logged a spurious
        # "PGVECTOR_CONNECTION_STRING variable not found" on every ingest /
        # retrieval, since the value lives only in the environment).
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={}, user_id=uuid.uuid4())
        called = {"variable_service": False}

        async def _fail_if_called(_name: str) -> str | None:
            called["variable_service"] = True
            return None

        backend.resolve_secret = _fail_if_called  # type: ignore[method-assign]
        await backend.ensure_ready()

        assert called["variable_service"] is False
        assert backend._resolved_connection_string == "postgresql+psycopg://user:pass@localhost:5432/db"

    async def test_ignores_tenant_supplied_env_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PGVECTOR_CONNECTION_STRING", "postgresql://u:p@db:5432/safe")
        monkeypatch.setenv("ATTACKER_SELECTED_ENV", "postgresql://u:p@db:5432/wrong")
        backend = create_backend(
            "postgres",
            kb_name="kb",
            kb_path=tmp_path,
            backend_config={"connection_string_variable": "ATTACKER_SELECTED_ENV"},
            user_id=uuid.uuid4(),
        )

        await backend._resolve_secrets()

        assert backend._resolved_connection_string == "postgresql+psycopg://u:p@db:5432/safe"

    async def test_missing_env_is_fatal(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={}, user_id=uuid.uuid4())
        with pytest.raises(ValueError, match="PGVECTOR_CONNECTION_STRING"):
            await backend.ensure_ready()


class TestEngineLifecycle:
    def test_engine_requires_ensure_ready_first(self, tmp_path: Path) -> None:
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={}, user_id=uuid.uuid4())
        with pytest.raises(RuntimeError, match="ensure_ready"):
            backend._ensure_async_engine()

    def test_engine_is_cached(self, make_backend) -> None:
        backend = make_backend(_FakeConn())
        assert backend._ensure_async_engine() is backend._ensure_async_engine()

    async def test_teardown_disposes_the_engine(self, make_backend) -> None:
        backend = make_backend(_FakeConn())
        engine = backend._pg_engine
        backend._vector_store = object()

        await backend.teardown()

        assert engine.disposed is True
        assert backend._pg_engine is None
        assert backend._vector_store is None

    async def test_teardown_swallows_dispose_errors(self, tmp_path: Path) -> None:
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={}, user_id=uuid.uuid4())
        backend._pg_engine = _FakeEngine(_FakeConn(), dispose_error=_DatabaseError("already closed"))

        await backend.teardown()  # must not raise

        assert backend._pg_engine is None

    async def test_teardown_without_an_engine_is_a_no_op(self, tmp_path: Path) -> None:
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={}, user_id=uuid.uuid4())
        await backend.teardown()
        assert backend._pg_engine is None


class TestRequirePgvector:
    def test_passes_when_the_client_is_importable(self, tmp_path: Path) -> None:
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={}, user_id=uuid.uuid4())
        assert backend._require_pgvector() is None

    def test_raises_an_install_hint_when_absent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # ``None`` in sys.modules is the documented way to make an import fail.
        monkeypatch.setitem(sys.modules, "pgvector.sqlalchemy", None)
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={}, user_id=uuid.uuid4())
        with pytest.raises(RuntimeError, match="pgvector extra"):
            backend._require_pgvector()


class TestEmbeddingTable:
    def test_columns_and_typed_dimension(self, make_backend) -> None:
        backend = make_backend()
        table = backend._embedding_table(1536)
        assert table.name == backend.table_name
        assert [column.name for column in table.columns] == ["id", "embedding", "document", "cmetadata"]
        assert str(table.c.embedding.type) == "VECTOR(1536)"

    def test_dimensionless_when_no_dim_given(self, make_backend) -> None:
        backend = make_backend()
        assert str(backend._embedding_table().c.embedding.type) == "VECTOR"


# --------------------------------------------------------------------------
# Table bootstrap (WS4: the operator owns the ``vector`` extension)
# --------------------------------------------------------------------------


class TestEnsureEmbeddingTable:
    @pytest.mark.parametrize("dim", [0, -1])
    async def test_rejects_non_positive_dimension(self, make_backend, dim: int) -> None:
        backend = make_backend(_FakeConn())
        with pytest.raises(ValueError, match="positive integer"):
            await backend._ensure_embedding_table(dim)

    async def test_creates_table_and_both_indexes(self, make_backend) -> None:
        conn = _FakeConn(table_exists=False, existing_dim=8)
        backend = make_backend(conn)

        await backend._ensure_embedding_table(8)

        joined = "\n".join(conn.statements)
        assert "pg_advisory_xact_lock" in joined  # DDL is serialized
        assert f'CREATE TABLE IF NOT EXISTS "{backend.table_name}"' in joined
        assert "embedding vector(8)" in joined
        assert f'"{backend.table_name}_cmeta_gin"' in joined
        assert f'"{backend.table_name}_hnsw"' in joined

    async def test_skips_hnsw_above_the_index_ceiling(self, make_backend) -> None:
        oversized = _HNSW_MAX_DIM + 1
        conn = _FakeConn(existing_dim=oversized)
        backend = make_backend(conn)

        await backend._ensure_embedding_table(oversized)

        joined = "\n".join(conn.statements)
        assert "_cmeta_gin" in joined  # metadata filtering still gets its index
        assert "hnsw" not in joined  # pgvector cannot index this width

    async def test_missing_extension_raises_the_shared_message_without_ddl(self, make_backend) -> None:
        conn = _FakeConn(ext_version=None)
        backend = make_backend(conn)

        with pytest.raises(ValueError, match="extension is not installed"):
            await backend._ensure_embedding_table(4)

        assert conn.statements  # the advisory lock was taken
        assert not any("CREATE" in sql for sql in conn.statements)

    async def test_dimension_change_is_reported_clearly(self, make_backend) -> None:
        # ``CREATE TABLE IF NOT EXISTS`` never widens an existing column, so a
        # swapped embedding model must be caught here rather than on INSERT.
        conn = _FakeConn(existing_dim=1536)
        backend = make_backend(conn, kb_name="research")

        with pytest.raises(ValueError, match="was created with 1536-dimensional embeddings"):
            await backend._ensure_embedding_table(768)

    async def test_matching_existing_dimension_is_accepted(self, make_backend) -> None:
        conn = _FakeConn(existing_dim=768)
        backend = make_backend(conn)
        await backend._ensure_embedding_table(768)
        assert any("_hnsw" in sql for sql in conn.statements)


class TestCatalogProbes:
    async def test_table_exists_reflects_to_regclass(self, make_backend) -> None:
        assert await make_backend(_FakeConn(table_exists=True))._table_exists(_FakeConn(table_exists=True)) is True
        assert await make_backend(_FakeConn())._table_exists(_FakeConn(table_exists=False)) is False

    async def test_existing_embedding_dim_parses_the_column_type(self, make_backend) -> None:
        backend = make_backend(_FakeConn())
        assert await backend._existing_embedding_dim(_FakeConn(existing_dim=384)) == 384
        assert await backend._existing_embedding_dim(_FakeConn(existing_dim=None)) is None

    async def test_vector_extension_installed(self, make_backend) -> None:
        backend = make_backend(_FakeConn())
        assert await backend._vector_extension_installed(_FakeConn(ext_version="0.8.0")) is True
        assert await backend._vector_extension_installed(_FakeConn(ext_version=None)) is False


class TestExtensionOwnership:
    """Langflow must never run ``CREATE EXTENSION`` on the operator's database."""

    def test_missing_extension_message_instructs_the_operator(self) -> None:
        assert "CREATE EXTENSION vector" in MISSING_EXTENSION_MESSAGE
        assert "only reads" in MISSING_EXTENSION_MESSAGE.lower()
        assert MISSING_EXTENSION_DETAILS_TYPE == "MissingExtension"

    def test_langflow_never_auto_creates_the_extension(self) -> None:
        import inspect

        from lfx.base.knowledge_bases.backends import postgres as pg_module

        # The removed auto-create clause must not creep back in. The operator
        # instruction ("CREATE EXTENSION vector") inside the message is allowed.
        assert "CREATE EXTENSION IF NOT EXISTS" not in inspect.getsource(pg_module)


class TestPgvectorVersionParsing:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("0.8.0", (0, 8, 0)),
            ("0.7.0", (0, 7, 0)),
            ("0.8", (0, 8, 0)),
            ("1", (1, 0, 0)),
            ("0.8.4-dev", (0, 8, 4)),
        ],
    )
    def test_parses_common_shapes(self, raw: str, expected: tuple[int, ...]) -> None:
        assert _parse_pgvector_version(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "garbage"])
    def test_unparseable_is_none(self, raw: str | None) -> None:
        assert _parse_pgvector_version(raw) is None

    def test_iterative_scan_threshold(self) -> None:
        # The gate the search path uses: 0.8.0 crossed, 0.7.x not.
        assert _parse_pgvector_version("0.8.0") >= (0, 8, 0)
        assert _parse_pgvector_version("0.7.9") < (0, 8, 0)


class TestDimensionErrorTranslation:
    def test_translates_the_raw_driver_message(self) -> None:
        friendly = _translate_dimension_error(
            RuntimeError("psycopg.errors: different vector dimensions 768 and 1536"),
            kb_name="kb",
            query_dim=768,
        )
        assert friendly == _dimension_mismatch_message("kb", existing_dim=1536, model_dim=768)

    def test_order_independent(self) -> None:
        # The existing dim is whichever number isn't the query dim, regardless of
        # the order pgvector prints them.
        friendly = _translate_dimension_error(
            RuntimeError("different vector dimensions 1536 and 768"),
            kb_name="kb",
            query_dim=768,
        )
        assert "was created with 1536-dimensional" in friendly

    def test_returns_none_for_unrelated_errors(self) -> None:
        assert _translate_dimension_error(RuntimeError("connection refused"), kb_name="kb", query_dim=8) is None


# --------------------------------------------------------------------------
# Writes and reads
# --------------------------------------------------------------------------


class TestAddDocuments:
    async def test_requires_an_embedding_function(self, make_backend) -> None:
        backend = make_backend(_FakeConn())
        with pytest.raises(ValueError, match="embedding function to add documents"):
            await backend._add_documents([Document(page_content="a")])

    async def test_rejects_a_vector_count_mismatch(self, make_backend) -> None:
        backend = make_backend(_FakeConn(), embeddings=_CountingEmbeddings(vectors=[[0.1, 0.2]]))
        with pytest.raises(ValueError, match="different number of vectors"):
            await backend._add_documents([Document(page_content="a"), Document(page_content="b")])

    async def test_no_documents_short_circuits_before_any_ddl(self, make_backend, fake_embeddings) -> None:
        conn = _FakeConn()
        backend = make_backend(conn, embeddings=fake_embeddings)

        assert await backend._add_documents([]) == []
        assert conn.statements == []

    async def test_rejects_an_id_count_mismatch(self, make_backend, fake_embeddings) -> None:
        backend = make_backend(_FakeConn(existing_dim=8), embeddings=fake_embeddings)
        with pytest.raises(ValueError, match="number of document ids"):
            await backend._add_documents([Document(page_content="a")], ids=["one", "two"])

    async def test_provisions_the_table_then_upserts(self, make_backend, fake_embeddings) -> None:
        conn = _FakeConn(existing_dim=8)
        backend = make_backend(conn, embeddings=fake_embeddings)

        returned = await backend._add_documents(
            [
                Document(page_content="cats are great", metadata={"topic": "cats"}),
                Document(page_content="dogs are loyal", metadata={"topic": "dogs"}),
            ]
        )

        assert len(returned) == 2
        joined = "\n".join(conn.statements)
        # The typed table is provisioned lazily, on the first write.
        assert "embedding vector(8)" in joined
        insert_sql = conn.statements[-1]
        assert f"INSERT INTO {backend.table_name}" in insert_sql
        assert "ON CONFLICT (id) DO UPDATE" in insert_sql
        # collection_id belonged to the old shared-table layout and must be gone.
        assert "collection_id" not in insert_sql

    async def test_honours_explicit_and_document_ids(self, make_backend, fake_embeddings) -> None:
        backend = make_backend(_FakeConn(existing_dim=8), embeddings=fake_embeddings)

        assert await backend._add_documents([Document(page_content="a")], ids=["explicit-id"]) == ["explicit-id"]
        assert await backend._add_documents([Document(id="doc-1", page_content="a")]) == ["doc-1"]
        generated = await backend._add_documents([Document(page_content="a")])
        assert uuid.UUID(generated[0])  # falls back to a fresh uuid4


class TestSimilaritySearch:
    async def test_requires_an_embedding_function(self, make_backend) -> None:
        backend = make_backend(_FakeConn())
        with pytest.raises(ValueError, match="embedding function to search"):
            await backend._similarity_search("q", k=1)

    async def test_empty_collection_returns_no_rows(self, make_backend, fake_embeddings) -> None:
        backend = make_backend(_FakeConn(table_exists=False), embeddings=fake_embeddings)
        assert await backend._similarity_search("q", k=3) == []

    async def test_returns_documents_with_distances(self, make_backend, fake_embeddings) -> None:
        rows = (
            SimpleNamespace(id="a", document="cats are great", cmetadata={"topic": "cats"}, distance=0.25),
            SimpleNamespace(id="b", document=None, cmetadata=None, distance=0.75),
        )
        conn = _FakeConn(select_rows=rows)
        backend = make_backend(conn, embeddings=fake_embeddings)

        results = await backend._similarity_search("feline", k=2)

        assert [(doc.id, doc.page_content, doc.metadata) for doc, _ in results] == [
            ("a", "cats are great", {"topic": "cats"}),
            ("b", "", {}),
        ]
        assert [score for _, score in results] == [0.25, 0.75]
        select_sql = conn.statements[-1]
        assert "<=>" in select_sql  # cosine distance, ordered for the HNSW index
        assert "LIMIT" in select_sql
        # No join back to a shared collection table any more.
        assert "langchain_pg_collection" not in select_sql

    async def test_metadata_filter_is_pushed_into_the_query(self, make_backend, fake_embeddings) -> None:
        conn = _FakeConn()
        backend = make_backend(conn, embeddings=fake_embeddings)

        await backend._similarity_search("q", k=1, filter={"topic": "cats"})

        assert "cmetadata @>" in conn.statements[-1]

    async def test_filtered_search_widens_the_hnsw_scan(self, make_backend, fake_embeddings) -> None:
        # pgvector filters *after* the HNSW candidate window, so a selective
        # filter can silently return < k rows. The filtered path widens
        # ``hnsw.ef_search`` (k * 40, capped) before the query.
        conn = _FakeConn()  # ext_version 0.7.0 -> no iterative scan available
        backend = make_backend(conn, embeddings=fake_embeddings)

        await backend._similarity_search("q", k=5, filter={"session_id": "s1"})

        joined = "\n".join(conn.statements)
        assert "SET LOCAL hnsw.ef_search = 200" in joined  # k(5) * 40
        assert "iterative_scan" not in joined  # server predates 0.8.0
        assert "cmetadata @>" in conn.statements[-1]  # filter is still executed in SQL

    async def test_filtered_search_enables_iterative_scan_on_08(self, make_backend, fake_embeddings) -> None:
        conn = _FakeConn(ext_version="0.8.0")
        backend = make_backend(conn, embeddings=fake_embeddings)

        await backend._similarity_search("q", k=1, filter={"session_id": "s1"})

        assert "SET LOCAL hnsw.iterative_scan = relaxed_order" in "\n".join(conn.statements)

    async def test_unfiltered_search_leaves_the_scan_gucs_alone(self, make_backend, fake_embeddings) -> None:
        conn = _FakeConn()
        backend = make_backend(conn, embeddings=fake_embeddings)

        await backend._similarity_search("q", k=3)

        joined = "\n".join(conn.statements)
        assert "ef_search" not in joined
        assert "iterative_scan" not in joined

    async def test_dimension_mismatch_on_retrieval_is_translated(self, make_backend, fake_embeddings) -> None:
        # ``fake_embeddings`` is 8-dim; the table reports a 1536-dim column, so
        # the driver raises. Retrieval must surface the same clear message ingest
        # does, as a non-retryable ``BackendConfigurationError``.
        class _DimConn(_FakeConn):
            async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeResult:  # noqa: ARG002
                sql = _render(statement)
                self.statements.append(sql)
                if "<=>" in sql:
                    msg = "different vector dimensions 8 and 1536"
                    raise RuntimeError(msg)
                return _FakeResult(())

        backend = make_backend(_DimConn(), embeddings=fake_embeddings)

        with pytest.raises(BackendConfigurationError, match="was created with 1536-dimensional"):
            await backend._similarity_search("q", k=1)

    async def test_vector_store_facade_delegates(self, make_backend, fake_embeddings) -> None:
        rows = (SimpleNamespace(id="a", document="hi", cmetadata={}, distance=0.5),)
        backend = make_backend(_FakeConn(select_rows=rows, existing_dim=8), embeddings=fake_embeddings)
        store = backend.vector_store

        assert isinstance(store, _PostgresVectorStore)
        assert store.embeddings is fake_embeddings
        assert await store.asimilarity_search("q", k=1) == [Document(id="a", page_content="hi", metadata={})]
        assert await store.asimilarity_search_with_score("q", k=1) == [
            (Document(id="a", page_content="hi", metadata={}), 0.5)
        ]
        assert await store.aadd_documents([Document(page_content="hi")], ids=["x"]) == ["x"]

    def test_vector_store_facade_rejects_the_sync_api(self, make_backend) -> None:
        store = make_backend().vector_store
        with pytest.raises(NotImplementedError, match="async"):
            store.similarity_search("q")
        with pytest.raises(NotImplementedError, match="PostgresBackend"):
            _PostgresVectorStore.from_texts(["a"])


# --------------------------------------------------------------------------
# Native metrics + lifecycle
# --------------------------------------------------------------------------


class TestCount:
    async def test_counts_rows(self, make_backend) -> None:
        assert await make_backend(_FakeConn(row_count=7)).count() == 7

    async def test_missing_table_counts_zero(self, make_backend) -> None:
        assert await make_backend(_FakeConn(table_exists=False)).count() == 0

    async def test_database_error_propagates(self, make_backend) -> None:
        # The "no table yet" case is handled by the explicit ``_table_exists``
        # check, so a genuine failure must surface rather than read as "0 chunks".
        with pytest.raises(_DatabaseError):
            await make_backend(_FakeConn(raise_on="count(*)")).count()


class TestIterDocuments:
    async def _collect(self, backend, **kwargs) -> list[list[IngestedDocument]]:
        return [batch async for batch in backend.iter_documents(**kwargs)]

    async def test_missing_table_yields_nothing(self, make_backend) -> None:
        backend = make_backend(_FakeConn(table_exists=False))
        assert await self._collect(backend) == []

    async def test_streams_in_batches(self, make_backend) -> None:
        rows = tuple((f"doc {i}", {"i": i}, None) for i in range(5))
        backend = make_backend(_FakeConn(stream_rows=rows))

        batches = await self._collect(backend, batch_size=2)

        assert [len(batch) for batch in batches] == [2, 2, 1]
        assert batches[0][0].content == "doc 0"
        assert batches[0][0].metadata == {"i": 0}
        assert batches[0][0].embedding is None

    async def test_includes_embeddings_on_request(self, make_backend) -> None:
        conn = _FakeConn(stream_rows=((None, None, "[0.1, 0.2]"),))
        backend = make_backend(conn)

        batches = await self._collect(backend, include_embeddings=True)

        assert batches[0][0].embedding == [0.1, 0.2]
        assert batches[0][0].content == ""
        assert batches[0][0].metadata == {}
        assert "embedding" in conn.statements[-1]

    async def test_database_error_propagates(self, make_backend) -> None:
        # A streaming failure must not masquerade as an empty KB (data loss).
        backend = make_backend(_FakeConn(raise_on="SELECT document"))
        with pytest.raises(_DatabaseError):
            await self._collect(backend)


class TestDeleteBy:
    async def test_empty_filter_is_a_no_op(self, make_backend) -> None:
        conn = _FakeConn()
        await make_backend(conn).delete_by({})
        assert conn.statements == []

    async def test_missing_table_is_a_no_op(self, make_backend) -> None:
        conn = _FakeConn(table_exists=False)
        await make_backend(conn).delete_by({"topic": "dogs"})
        assert not any("DELETE" in sql for sql in conn.statements)

    async def test_deletes_by_metadata_containment(self, make_backend) -> None:
        conn = _FakeConn()
        backend = make_backend(conn)

        await backend.delete_by({"topic": "dogs"})

        assert conn.statements[-1].startswith(f"DELETE FROM {backend.table_name}")  # noqa: S608
        assert "cmetadata @> CAST(:where AS jsonb)" in conn.statements[-1]

    async def test_database_error_is_raised(self, make_backend) -> None:
        backend = make_backend(_FakeConn(raise_on="DELETE FROM"))
        with pytest.raises(_DatabaseError):
            await backend.delete_by({"topic": "dogs"})


class TestStorageSize:
    async def test_reports_total_relation_size(self, make_backend) -> None:
        assert await make_backend(_FakeConn(storage_size=4096)).storage_size_bytes() == 4096

    async def test_database_error_reports_zero(self, make_backend) -> None:
        assert await make_backend(_FakeConn(raise_on="pg_total_relation_size")).storage_size_bytes() == 0


class TestDeleteCollection:
    async def test_drops_the_table(self, make_backend) -> None:
        conn = _FakeConn()
        backend = make_backend(conn)

        await backend.delete_collection()

        assert conn.statements[-1] == f'DROP TABLE IF EXISTS "{backend.table_name}"'

    async def test_database_error_is_raised(self, make_backend) -> None:
        backend = make_backend(_FakeConn(raise_on="DROP TABLE"))
        with pytest.raises(_DatabaseError):
            await backend.delete_collection()


class TestTestConnection:
    async def test_missing_env_is_a_config_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # No connection string anywhere -> ensure_ready raises ValueError, which
        # test_connection maps to a clean ConfigError result (no DB contacted).
        monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={}, user_id=None)

        result = await backend.test_connection()

        assert result.ok is False
        assert result.details.get("type") == "ConfigError"

    async def test_setup_failure_is_structured(self, make_backend) -> None:
        backend = make_backend(_FakeConn())

        def _raise_setup_error():
            msg = "unsupported driver"
            raise ValueError(msg)

        backend._ensure_async_engine = _raise_setup_error

        result = await backend.test_connection()

        assert result.ok is False
        assert result.message == "Postgres backend setup failed."
        assert result.details == {"type": "SetupError", "error_type": "ValueError"}

    async def test_missing_pgvector_client_is_reported_verbatim(
        self, make_backend, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "pgvector.sqlalchemy", None)
        backend = make_backend(_FakeConn())

        result = await backend.test_connection()

        assert result.ok is False
        assert "pgvector extra" in result.message
        assert result.details["error_type"] == "RuntimeError"

    async def test_unreachable_database_is_friendly(self, make_backend) -> None:
        backend = make_backend(_FakeConn(raise_on="SELECT 1"))

        result = await backend.test_connection()

        assert result.ok is False
        assert "PGVECTOR_CONNECTION_STRING" in result.message
        assert result.details["type"] == "_DatabaseError"

    async def test_missing_extension_uses_the_shared_message(self, make_backend) -> None:
        backend = make_backend(_FakeConn(ext_version=None))

        result = await backend.test_connection()

        assert result.ok is False
        assert result.message == MISSING_EXTENSION_MESSAGE
        assert result.details == {"type": MISSING_EXTENSION_DETAILS_TYPE}

    async def test_ok_when_the_extension_is_present(self, make_backend) -> None:
        backend = make_backend(_FakeConn(ext_version="0.7.0", server_version="16.1"))

        result = await backend.test_connection()

        assert result.ok is True
        assert "0.7.0" in result.message
        assert result.details == {"server_version": "16.1", "pgvector_version": "0.7.0"}

    async def test_missing_create_privilege_is_reported(self, make_backend) -> None:
        # Extension present but the role can't create tables -> ingest would fail
        # on first write; report it here instead of "Configured and reachable".
        backend = make_backend(_FakeConn(ext_version="0.8.0", server_version="16.1", can_create=False))

        result = await backend.test_connection()

        assert result.ok is False
        assert result.message == MISSING_CREATE_PRIVILEGE_MESSAGE
        assert result.details == {"type": MISSING_CREATE_PRIVILEGE_DETAILS_TYPE}

    async def test_unknown_create_privilege_does_not_fail_the_check(self, make_backend) -> None:
        # A ``None`` probe result (e.g. no current schema) must not false-alarm.
        backend = make_backend(_FakeConn(ext_version="0.8.0", server_version="16.1", can_create=None))

        result = await backend.test_connection()

        assert result.ok is True
