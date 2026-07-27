"""Unit + integration tests for the pgVector (``PostgresBackend``).

The pure-logic tests always run. The integration class is gated on a reachable
pgvector database: set ``PGVECTOR_CONNECTION_STRING`` (and install the pgvector
extra) to exercise the real add / search / count / iter / delete path; it skips
cleanly otherwise.
"""

from __future__ import annotations

import contextlib
import os
import uuid
from typing import TYPE_CHECKING

import pytest
from lfx.base.knowledge_bases.backends import BackendType, PostgresBackend, create_backend
from lfx.base.knowledge_bases.backends.postgres import (
    _COUNT_SQL,
    _DELETE_BY_SQL,
    _DELETE_COLLECTION_SQL,
    _coerce_embedding,
    _iter_documents_sql,
    _normalize_driver,
    postgres_env_configured,
    read_connection_string_from_env,
)

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

    def test_not_configured_when_env_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
        assert postgres_env_configured() is False
        assert read_connection_string_from_env() is None


class TestPostgresSql:
    def test_queries_use_literal_tables_and_bound_params(self) -> None:
        assert "langchain_pg_embedding" in _COUNT_SQL
        assert "langchain_pg_collection" in _COUNT_SQL
        assert ":name" in _COUNT_SQL
        assert ":name" in _DELETE_BY_SQL
        assert ":where" in _DELETE_BY_SQL
        assert ":name" in _DELETE_COLLECTION_SQL

    def test_iter_sql_selects_embedding_only_when_requested(self) -> None:
        assert "e.embedding" not in _iter_documents_sql(include_embeddings=False)
        assert "e.embedding" in _iter_documents_sql(include_embeddings=True)


class TestCoerceEmbedding:
    def test_list_passthrough(self) -> None:
        assert _coerce_embedding([0.1, 0.2]) == [0.1, 0.2]

    def test_pgvector_string_repr(self) -> None:
        assert _coerce_embedding("[0.1, 0.2, 0.3]") == [0.1, 0.2, 0.3]

    def test_none_and_garbage(self) -> None:
        assert _coerce_embedding(None) is None
        assert _coerce_embedding("not-a-vector") is None


class TestPostgresCollectionAndConfig:
    def test_backend_type_and_collection_is_kb_name(self, tmp_path: Path) -> None:
        backend = create_backend("postgres", kb_name="my_kb", kb_path=tmp_path, backend_config={})
        assert isinstance(backend, PostgresBackend)
        assert backend.backend_type is BackendType.POSTGRES
        assert backend.kb_name == "my_kb"

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

    async def test_falls_back_to_variable_service_when_env_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # When the env var is unset, deployments that store the connection string
        # as a Langflow variable are still honored via resolve_secret.
        monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
        backend = create_backend("postgres", kb_name="kb", kb_path=tmp_path, backend_config={}, user_id=uuid.uuid4())

        async def _from_variable_service(_name: str) -> str:
            return "postgresql://u:p@db:5432/x"

        backend.resolve_secret = _from_variable_service  # type: ignore[method-assign]
        await backend._resolve_secrets()

        assert backend._resolved_connection_string == "postgresql+psycopg://u:p@db:5432/x"


# --------------------------------------------------------------------------
# Integration: requires a reachable pgvector database.
# --------------------------------------------------------------------------


def _require_live_pgvector() -> str:
    conn = os.getenv("PGVECTOR_CONNECTION_STRING")
    if not conn:
        pytest.skip("PGVECTOR_CONNECTION_STRING not set — skipping live pgvector integration test")
    try:
        import pgvector  # noqa: F401
    except ImportError:
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
            "postgres", kb_name=kb_name, kb_path=tmp_path, backend_config={}, embedding_function=fake_embeddings
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
