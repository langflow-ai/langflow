"""Unit + integration tests for the pgVector (``PostgresBackend``).

The pure-logic tests always run. The integration class is gated on an explicit
opt-in plus a reachable pgvector database: set
``LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1`` and
``PGVECTOR_CONNECTION_STRING`` (and install the pgvector extra) to exercise the
real add / search / count / iter / delete path; it skips cleanly otherwise.
"""

from __future__ import annotations

import contextlib
import os
import uuid
from typing import TYPE_CHECKING

import pytest
from lfx.base.knowledge_bases.backends import BackendType, PostgresBackend, create_backend
from lfx.base.knowledge_bases.backends.postgres import (
    MISSING_EXTENSION_DETAILS_TYPE,
    MISSING_EXTENSION_MESSAGE,
    _coerce_embedding,
    _count_sql,
    _delete_by_sql,
    _drop_table_sql,
    _iter_documents_sql,
    _normalize_driver,
    _parse_vector_dim,
    _validate_table_name,
    postgres_env_configured,
    read_connection_string_from_env,
    resolve_default_kb_backend,
)

# A syntactically valid collection table name (``lf_`` + 24 hex).
_VALID_TABLE = "lf_0123456789abcdef01234567"

if TYPE_CHECKING:
    from pathlib import Path


class TestPostgresDriverNormalization:
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


class TestPostgresEnvDetection:
    def test_configured_when_env_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PGVECTOR_CONNECTION_STRING", "postgresql://u:p@h/db")
        assert postgres_env_configured() is True
        assert read_connection_string_from_env() == "postgresql://u:p@h/db"
        assert resolve_default_kb_backend() == BackendType.POSTGRES.value

    def test_not_configured_when_env_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
        assert postgres_env_configured() is False
        assert read_connection_string_from_env() is None
        assert resolve_default_kb_backend() == BackendType.CHROMA.value


class TestPostgresSql:
    def test_queries_target_the_per_collection_table(self) -> None:
        count_sql = _count_sql(_VALID_TABLE)
        assert count_sql.startswith("SELECT count(*) FROM ")
        assert count_sql.endswith(_VALID_TABLE)
        # ``where`` stays a bound parameter; only the validated table name is interpolated.
        delete_sql = _delete_by_sql(_VALID_TABLE)
        assert _VALID_TABLE in delete_sql
        assert ":where" in delete_sql
        assert _VALID_TABLE in _drop_table_sql(_VALID_TABLE)

    def test_iter_sql_selects_embedding_only_when_requested(self) -> None:
        assert "embedding" not in _iter_documents_sql(_VALID_TABLE, include_embeddings=False)
        assert "embedding" in _iter_documents_sql(_VALID_TABLE, include_embeddings=True)
        assert _VALID_TABLE in _iter_documents_sql(_VALID_TABLE, include_embeddings=True)

    @pytest.mark.parametrize(
        "bad_name",
        [
            "langchain_pg_embedding",  # not an lf_ hash
            "lf_short",
            "lf_0123456789abcdef01234567; DROP TABLE users",  # injection attempt
            "lf_0123456789ABCDEF01234567",  # uppercase hex rejected
            "LF_0123456789abcdef01234567",
        ],
    )
    def test_rejects_unexpected_table_name(self, bad_name: str) -> None:
        with pytest.raises(ValueError, match="collection table name"):
            _validate_table_name(bad_name)
        with pytest.raises(ValueError, match="collection table name"):
            _count_sql(bad_name)

    def test_accepts_valid_table_name(self) -> None:
        assert _validate_table_name(_VALID_TABLE) == _VALID_TABLE


class TestParseVectorDim:
    def test_parses_dimension(self) -> None:
        assert _parse_vector_dim("vector(1536)") == 1536

    def test_dimensionless_and_garbage(self) -> None:
        assert _parse_vector_dim("vector") is None
        assert _parse_vector_dim(None) is None
        assert _parse_vector_dim("text") is None


class TestCoerceEmbedding:
    def test_list_passthrough(self) -> None:
        assert _coerce_embedding([0.1, 0.2]) == [0.1, 0.2]

    def test_pgvector_string_repr(self) -> None:
        assert _coerce_embedding("[0.1, 0.2, 0.3]") == [0.1, 0.2, 0.3]

    def test_none_and_garbage(self) -> None:
        assert _coerce_embedding(None) is None
        assert _coerce_embedding("not-a-vector") is None


class TestPostgresCollectionAndConfig:
    def test_cosine_distance_score_is_normalized_to_higher_is_better(self, tmp_path: Path) -> None:
        backend = create_backend(
            "postgres",
            kb_name="scores",
            kb_path=tmp_path,
            backend_config={},
            user_id=uuid.uuid4(),
        )
        assert backend.normalize_score(0.25) == -0.25

    def test_backend_type_and_collection_is_scoped_to_owner(self, tmp_path: Path) -> None:
        owner_id = uuid.uuid4()
        backend = create_backend(
            "postgres",
            kb_name="my_kb",
            kb_path=tmp_path,
            backend_config={},
            user_id=owner_id,
        )
        assert isinstance(backend, PostgresBackend)
        assert backend.backend_type is BackendType.POSTGRES
        assert backend.collection_name.startswith("lf_")
        assert backend.collection_name != "my_kb"

    def test_same_kb_name_isolated_between_owners(self, tmp_path: Path) -> None:
        first = create_backend(
            "postgres",
            kb_name="shared",
            kb_path=tmp_path,
            backend_config={},
            user_id=uuid.uuid4(),
        )
        second = create_backend(
            "postgres",
            kb_name="shared",
            kb_path=tmp_path,
            backend_config={},
            user_id=uuid.uuid4(),
        )
        assert first.collection_name != second.collection_name

    def test_collection_requires_valid_owner(self, tmp_path: Path) -> None:
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={})
        with pytest.raises(ValueError, match="valid user_id"):
            _ = backend.collection_name

    async def test_test_connection_missing_env_is_config_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No connection string anywhere -> ensure_ready raises ValueError, which
        # test_connection maps to a clean ConfigError result (no DB contacted).
        monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={}, user_id=None)
        result = await backend.test_connection()
        assert result.ok is False
        assert result.details.get("type") == "ConfigError"

    async def test_test_connection_setup_error_is_structured(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PGVECTOR_CONNECTION_STRING", "postgresql://u:p@localhost:5432/db")
        backend = create_backend(
            "postgres",
            kb_name="kb",
            kb_path=tmp_path,
            backend_config={},
            user_id=uuid.uuid4(),
        )

        def _raise_setup_error():
            msg = "unsupported driver"
            raise ValueError(msg)

        # Bypass the optional-dependency check so the engine-setup failure (not a
        # missing pgvector extra) is what drives the SetupError branch.
        monkeypatch.setattr(backend, "_require_pgvector", lambda: None)
        monkeypatch.setattr(backend, "_ensure_async_engine", _raise_setup_error)

        result = await backend.test_connection()

        assert result.ok is False
        assert result.message == "Postgres backend setup failed."
        assert result.details == {"type": "SetupError", "error_type": "ValueError"}

    async def test_env_connection_string_skips_variable_service(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # pgVector is env-driven: when the env var is set, resolution must NOT
        # query the variable service (doing so logged a spurious
        # "PGVECTOR_CONNECTION_STRING variable not found" on every ingest /
        # retrieval, since the value lives only in the environment).
        monkeypatch.setenv("PGVECTOR_CONNECTION_STRING", "postgresql://u:p@localhost:5432/db")
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={}, user_id=uuid.uuid4())

        called = {"variable_service": False}

        async def _fail_if_called(_name: str) -> str | None:
            called["variable_service"] = True
            return None

        backend.resolve_secret = _fail_if_called  # type: ignore[method-assign]
        await backend._resolve_secrets()

        assert called["variable_service"] is False
        assert backend._resolved_connection_string == "postgresql+psycopg://u:p@localhost:5432/db"

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


class _FakeConn:
    """Minimal async connection stub for the extension-ownership unit tests."""

    def __init__(self, *, ext_version: str | None = None, server_version: str = "16.1") -> None:
        self._ext_version = ext_version
        self._server_version = server_version
        self.executed: list[str] = []

    async def execute(self, statement, params=None):  # noqa: ARG002
        self.executed.append(str(statement))

    async def scalar(self, statement, params=None):  # noqa: ARG002
        sql = str(statement)
        if "extversion" in sql:
            return self._ext_version
        if "server_version" in sql:
            return self._server_version
        return None


class _FakeAcm:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _FakeEngine:
    """Stub engine whose ``connect``/``begin`` both yield the same fake conn."""

    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def connect(self) -> _FakeAcm:
        return _FakeAcm(self._conn)

    def begin(self) -> _FakeAcm:
        return _FakeAcm(self._conn)


class TestPostgresExtensionOwnership:
    """WS4: the operator owns the ``vector`` extension; Langflow only checks it.

    Langflow must never run ``CREATE EXTENSION`` on the operator's database, and
    every site that finds the extension missing surfaces one shared, actionable
    message so the fix is always the same clear step.
    """

    def test_missing_extension_message_instructs_the_operator(self) -> None:
        assert "CREATE EXTENSION vector" in MISSING_EXTENSION_MESSAGE
        # The separation of duties is spelled out for the reader.
        assert "only reads" in MISSING_EXTENSION_MESSAGE.lower()
        assert MISSING_EXTENSION_DETAILS_TYPE == "MissingExtension"

    def test_langflow_never_auto_creates_the_extension(self) -> None:
        import inspect

        from lfx.base.knowledge_bases.backends import postgres as pg_module

        source = inspect.getsource(pg_module)
        # The removed auto-create clause must not creep back in. The operator
        # instruction ("CREATE EXTENSION vector") inside the message is allowed.
        assert "CREATE EXTENSION IF NOT EXISTS" not in source

    async def test_test_connection_missing_extension_uses_shared_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PGVECTOR_CONNECTION_STRING", "postgresql://u:p@localhost:5432/db")
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={}, user_id=uuid.uuid4())
        conn = _FakeConn(ext_version=None)
        monkeypatch.setattr(backend, "_require_pgvector", lambda: None)
        monkeypatch.setattr(backend, "_ensure_async_engine", lambda: _FakeEngine(conn))

        result = await backend.test_connection()

        assert result.ok is False
        assert result.message == MISSING_EXTENSION_MESSAGE
        assert result.details == {"type": MISSING_EXTENSION_DETAILS_TYPE}

    async def test_test_connection_ok_when_extension_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PGVECTOR_CONNECTION_STRING", "postgresql://u:p@localhost:5432/db")
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={}, user_id=uuid.uuid4())
        conn = _FakeConn(ext_version="0.7.0", server_version="16.1")
        monkeypatch.setattr(backend, "_require_pgvector", lambda: None)
        monkeypatch.setattr(backend, "_ensure_async_engine", lambda: _FakeEngine(conn))

        result = await backend.test_connection()

        assert result.ok is True
        assert "0.7.0" in result.message

    async def test_ingest_setup_raises_shared_message_without_creating(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # First-ingest table setup must fail clearly (not with a cryptic "type
        # vector does not exist") and must not issue any DDL when the operator
        # has not installed the extension.
        monkeypatch.setenv("PGVECTOR_CONNECTION_STRING", "postgresql://u:p@localhost:5432/db")
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={}, user_id=uuid.uuid4())
        conn = _FakeConn(ext_version=None)  # exercises the real _vector_extension_installed helper
        monkeypatch.setattr(backend, "_require_pgvector", lambda: None)
        monkeypatch.setattr(backend, "_ensure_async_engine", lambda: _FakeEngine(conn))

        with pytest.raises(ValueError, match="extension is not installed"):
            await backend._ensure_embedding_table(4)

        assert conn.executed  # the advisory lock was taken
        assert not any("CREATE" in sql for sql in conn.executed)  # no CREATE TABLE/INDEX/EXTENSION


# --------------------------------------------------------------------------
# Integration: requires a reachable pgvector database.
# --------------------------------------------------------------------------


def _require_live_pgvector() -> str:
    if os.getenv("LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS") != "1":
        pytest.skip("Set LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1 to run live pgvector tests")
    conn = os.getenv("PGVECTOR_CONNECTION_STRING")
    if not conn:
        pytest.skip("PGVECTOR_CONNECTION_STRING not set — skipping live pgvector integration test")
    try:
        import pgvector  # noqa: F401
        from pgvector.sqlalchemy import Vector  # noqa: F401
    except (ImportError, RuntimeError):
        pytest.skip("pgvector client package not installed — install the pgvector extra")
    return conn


@pytest.fixture
def fake_embeddings():
    from langchain_core.embeddings import DeterministicFakeEmbedding

    return DeterministicFakeEmbedding(size=16)


class TestPostgresBackendLive:
    """Exercises the real vector path against a pgvector database when available."""

    async def test_full_lifecycle(self, tmp_path: Path, fake_embeddings) -> None:
        _require_live_pgvector()
        from langchain_core.documents import Document

        kb_name = f"kb_it_{uuid.uuid4().hex[:8]}"
        backend = create_backend(
            "postgres",
            kb_name=kb_name,
            kb_path=tmp_path,
            backend_config={},
            embedding_function=fake_embeddings,
            user_id=uuid.uuid4(),
        )
        try:
            await backend.ensure_ready()
            tc = await backend.test_connection()
            if not tc.ok:
                pytest.skip(f"pgvector not reachable: {tc.message}")

            await backend.add_documents(
                [
                    Document(page_content="cats are great", metadata={"topic": "cats"}),
                    Document(page_content="dogs are loyal", metadata={"topic": "dogs"}),
                ]
            )
            assert await backend.count() == 2

            results = await backend.similarity_search("feline", k=1, with_scores=True)
            assert len(results) == 1  # inherited base similarity_search path

            streamed = 0
            async for batch in backend.iter_documents(batch_size=1):
                streamed += len(batch)
            assert streamed == 2

            await backend.delete_by({"topic": "dogs"})
            assert await backend.count() == 1
        finally:
            with contextlib.suppress(Exception):
                await backend.delete_collection()
            await backend.teardown()

    async def test_hnsw_index_created_on_ingest(self, tmp_path: Path, fake_embeddings) -> None:
        _require_live_pgvector()
        from langchain_core.documents import Document
        from sqlalchemy import text

        backend = create_backend(
            "postgres",
            kb_name=f"kb_idx_{uuid.uuid4().hex[:8]}",
            kb_path=tmp_path,
            backend_config={},
            embedding_function=fake_embeddings,
            user_id=uuid.uuid4(),
        )
        try:
            await backend.ensure_ready()
            tc = await backend.test_connection()
            if not tc.ok:
                pytest.skip(f"pgvector not reachable: {tc.message}")

            await backend.add_documents([Document(page_content="hello", metadata={})])

            engine = backend._ensure_async_engine()
            async with engine.connect() as conn:
                index_defs = (
                    (
                        await conn.execute(
                            text("SELECT indexdef FROM pg_indexes WHERE tablename = :name"),
                            {"name": backend.table_name},
                        )
                    )
                    .scalars()
                    .all()
                )
            # A 16-dim table (well under the HNSW ceiling) must carry an HNSW index.
            assert any("hnsw" in definition.lower() for definition in index_defs), index_defs
        finally:
            with contextlib.suppress(Exception):
                await backend.delete_collection()
            await backend.teardown()

    async def test_similarity_search_plan_uses_hnsw_index(self, tmp_path: Path, fake_embeddings) -> None:
        _require_live_pgvector()
        from langchain_core.documents import Document
        from sqlalchemy import text

        backend = create_backend(
            "postgres",
            kb_name=f"kb_plan_{uuid.uuid4().hex[:8]}",
            kb_path=tmp_path,
            backend_config={},
            embedding_function=fake_embeddings,
            user_id=uuid.uuid4(),
        )
        try:
            await backend.ensure_ready()
            tc = await backend.test_connection()
            if not tc.ok:
                pytest.skip(f"pgvector not reachable: {tc.message}")

            await backend.add_documents([Document(page_content=f"doc {i}", metadata={}) for i in range(50)])

            query_vector = await fake_embeddings.aembed_query("doc 1")
            literal = "[" + ",".join(str(v) for v in query_vector) + "]"
            engine = backend._ensure_async_engine()
            async with engine.begin() as conn:
                # Force the planner to prefer the ANN index for this tiny table so
                # the assertion is about "is the index usable", not planner cost.
                await conn.execute(text("SET LOCAL enable_seqscan = off"))
                plan_rows = (
                    (
                        await conn.execute(
                            text(
                                f'EXPLAIN SELECT id FROM "{backend.table_name}" '  # noqa: S608 — validated name
                                f"ORDER BY embedding <=> '{literal}'::vector LIMIT 5"
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
            plan = "\n".join(plan_rows)
            assert f"{backend.table_name}_hnsw" in plan, plan
        finally:
            with contextlib.suppress(Exception):
                await backend.delete_collection()
            await backend.teardown()

    async def test_mixed_embedding_dimensions_coexist(self, tmp_path: Path) -> None:
        _require_live_pgvector()
        from langchain_core.documents import Document
        from langchain_core.embeddings import DeterministicFakeEmbedding

        # Two KBs on the same deployment using different embedding dimensions.
        # The shared-table layout could not do this; per-collection typed tables can.
        small = create_backend(
            "postgres",
            kb_name=f"kb_small_{uuid.uuid4().hex[:8]}",
            kb_path=tmp_path,
            backend_config={},
            embedding_function=DeterministicFakeEmbedding(size=8),
            user_id=uuid.uuid4(),
        )
        large = create_backend(
            "postgres",
            kb_name=f"kb_large_{uuid.uuid4().hex[:8]}",
            kb_path=tmp_path,
            backend_config={},
            embedding_function=DeterministicFakeEmbedding(size=32),
            user_id=uuid.uuid4(),
        )
        try:
            await small.ensure_ready()
            tc = await small.test_connection()
            if not tc.ok:
                pytest.skip(f"pgvector not reachable: {tc.message}")

            assert small.table_name != large.table_name
            await small.add_documents([Document(page_content="a", metadata={})])
            await large.add_documents([Document(page_content="b", metadata={})])

            assert await small.count() == 1
            assert await large.count() == 1
            assert len(await small.similarity_search("a", k=1)) == 1
            assert len(await large.similarity_search("b", k=1)) == 1
        finally:
            for backend in (small, large):
                with contextlib.suppress(Exception):
                    await backend.delete_collection()
                await backend.teardown()
