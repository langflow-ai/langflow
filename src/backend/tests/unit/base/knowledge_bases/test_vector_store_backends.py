"""Phase 4 backend unit tests.

Covers the three DB-connector backends — MongoDB, Astra, and
Postgres — plus the ``create_backend`` dispatch path that
``perform_ingestion`` + retrieval now route through.

Each backend's LangChain vectorstore dep is imported lazily, so the
tests stub those modules via ``sys.modules`` injection rather than
pulling real drivers. This keeps the suite credential-free and fast.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest
from lfx.base.knowledge_bases.backends import (
    AstraBackend,
    BackendType,
    MongoDBBackend,
    PostgresBackend,
    create_backend,
    registered_backends,
)


class TestRegistry:
    """Phase 0's registry now resolves all four backend identifiers."""

    def test_every_phase4_backend_registered(self):
        registered = set(registered_backends())
        assert BackendType.CHROMA in registered
        assert BackendType.MONGODB in registered
        assert BackendType.ASTRA in registered
        assert BackendType.POSTGRES in registered

    def test_create_backend_dispatches_by_string(self, tmp_path):
        # String dispatch makes DB rows and API payloads round-trip
        # cleanly without imports at the caller.
        mongo = create_backend("mongodb", kb_name="kb", kb_path=tmp_path)
        assert isinstance(mongo, MongoDBBackend)

        astra = create_backend("astra", kb_name="kb", kb_path=tmp_path)
        assert isinstance(astra, AstraBackend)

        pg = create_backend("postgres", kb_name="kb", kb_path=tmp_path)
        assert isinstance(pg, PostgresBackend)


# --------------------------------------------------------------------
# MongoDB
# --------------------------------------------------------------------


class TestMongoDBBackendValidation:
    async def test_build_requires_database(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MONGODB_ATLAS_URI", "mongodb+srv://demo")
        backend = MongoDBBackend(
            kb_name="kb",
            kb_path=tmp_path,
            backend_config={"collection": "c"},
        )
        with pytest.raises(ValueError, match="'database'"):
            backend._build_vector_store()

    async def test_build_requires_connection_variable(self, tmp_path, monkeypatch):
        monkeypatch.delenv("MONGODB_ATLAS_URI", raising=False)
        backend = MongoDBBackend(
            kb_name="kb",
            kb_path=tmp_path,
            backend_config={"database": "d", "collection": "c"},
        )
        with pytest.raises(ValueError, match="MONGODB_ATLAS_URI"):
            backend._build_vector_store()


class TestMongoDBBackendBuild:
    async def test_build_instantiates_langchain_and_pymongo(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MONGODB_ATLAS_URI", "mongodb+srv://demo")

        fake_collection = MagicMock(name="mongo_collection")
        fake_db = MagicMock(name="mongo_db")
        fake_db.__getitem__.return_value = fake_collection
        fake_client = MagicMock(name="mongo_client")
        fake_client.__getitem__.return_value = fake_db

        pymongo_module = types.ModuleType("pymongo")
        pymongo_module.MongoClient = MagicMock(return_value=fake_client)

        langchain_mongo_module = types.ModuleType("langchain_mongodb")
        fake_store = MagicMock(name="vector_store")
        langchain_mongo_module.MongoDBAtlasVectorSearch = MagicMock(return_value=fake_store)

        monkeypatch.setitem(sys.modules, "pymongo", pymongo_module)
        monkeypatch.setitem(sys.modules, "langchain_mongodb", langchain_mongo_module)

        backend = MongoDBBackend(
            kb_name="kb",
            kb_path=tmp_path,
            backend_config={
                "database": "my_db",
                "collection": "my_col",
                "index_name": "my_index",
            },
            embedding_function=MagicMock(),
        )
        built = backend._build_vector_store()

        pymongo_module.MongoClient.assert_called_once_with("mongodb+srv://demo")
        langchain_mongo_module.MongoDBAtlasVectorSearch.assert_called_once()
        kwargs = langchain_mongo_module.MongoDBAtlasVectorSearch.call_args.kwargs
        assert kwargs["collection"] is fake_collection
        assert kwargs["index_name"] == "my_index"
        assert built is fake_store
        # Teardown should close the pymongo client.
        await backend.teardown()
        fake_client.close.assert_called_once()


# --------------------------------------------------------------------
# Astra
# --------------------------------------------------------------------


class TestAstraBackendValidation:
    async def test_missing_collection_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://x.apps.astra.datastax.com")
        monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "AstraCS:demo")
        backend = AstraBackend(kb_name="kb", kb_path=tmp_path, backend_config={})
        with pytest.raises(ValueError, match="'collection_name'"):
            backend._build_vector_store()

    async def test_missing_token_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://x.apps.astra.datastax.com")
        monkeypatch.delenv("ASTRA_DB_APPLICATION_TOKEN", raising=False)
        backend = AstraBackend(
            kb_name="kb",
            kb_path=tmp_path,
            backend_config={"collection_name": "c"},
        )
        with pytest.raises(ValueError, match="ASTRA_DB_APPLICATION_TOKEN"):
            backend._build_vector_store()


class TestAstraBackendBuild:
    async def test_build_instantiates_astra_vector_store(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://x.apps.astra.datastax.com")
        monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "AstraCS:demo")

        fake_store = MagicMock(name="astra_vector_store")
        module = types.ModuleType("langchain_astradb")
        module.AstraDBVectorStore = MagicMock(return_value=fake_store)
        monkeypatch.setitem(sys.modules, "langchain_astradb", module)

        backend = AstraBackend(
            kb_name="kb",
            kb_path=tmp_path,
            backend_config={"collection_name": "c", "namespace": "ns"},
            embedding_function=MagicMock(),
        )
        built = backend._build_vector_store()
        assert built is fake_store
        module.AstraDBVectorStore.assert_called_once()
        kwargs = module.AstraDBVectorStore.call_args.kwargs
        assert kwargs["collection_name"] == "c"
        assert kwargs["namespace"] == "ns"
        assert kwargs["token"] == "AstraCS:demo"  # noqa: S105 — fake token for test  # pragma: allowlist secret
        assert kwargs["api_endpoint"] == "https://x.apps.astra.datastax.com"


# --------------------------------------------------------------------
# Postgres
# --------------------------------------------------------------------


class TestPostgresBackendValidation:
    async def test_missing_collection_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("POSTGRES_CONNECTION_URL", "postgresql://demo")
        backend = PostgresBackend(kb_name="kb", kb_path=tmp_path, backend_config={})
        with pytest.raises(ValueError, match="'collection_name'"):
            backend._build_vector_store()

    async def test_missing_connection_variable_raises(self, tmp_path, monkeypatch):
        monkeypatch.delenv("POSTGRES_CONNECTION_URL", raising=False)
        backend = PostgresBackend(
            kb_name="kb",
            kb_path=tmp_path,
            backend_config={"collection_name": "c"},
        )
        with pytest.raises(ValueError, match="POSTGRES_CONNECTION_URL"):
            backend._build_vector_store()


class TestPostgresBackendBuild:
    async def test_build_instantiates_pgvector(self, tmp_path, monkeypatch):
        monkeypatch.setenv("POSTGRES_CONNECTION_URL", "postgresql://demo")

        fake_store = MagicMock(name="pg_store")
        module = types.ModuleType("langchain_postgres")
        module.PGVector = MagicMock(return_value=fake_store)
        monkeypatch.setitem(sys.modules, "langchain_postgres", module)

        backend = PostgresBackend(
            kb_name="kb",
            kb_path=tmp_path,
            backend_config={"collection_name": "my_kb"},
            embedding_function=MagicMock(),
        )
        built = backend._build_vector_store()
        assert built is fake_store
        kwargs = module.PGVector.call_args.kwargs
        assert kwargs["collection_name"] == "my_kb"
        assert kwargs["connection"] == "postgresql://demo"
        assert kwargs["use_jsonb"] is True


# --------------------------------------------------------------------
# Missing optional dep messaging
# --------------------------------------------------------------------


class TestMissingOptionalDepsSurfaceHelpfulErrors:
    """Missing optional deps surface as actionable RuntimeErrors.

    When the LangChain adapter package isn't installed, each backend
    should raise a ``RuntimeError`` naming the missing install — not
    a cryptic ``ImportError``.
    """

    def _hide_module(self, monkeypatch, name: str) -> None:
        """Make ``import <name>`` fail via sys.modules injection."""

        class _MissingModule(types.ModuleType):
            def __getattr__(self, attr):  # pragma: no cover — always raises
                msg = f"module '{name}' has no attribute {attr!r}"
                raise AttributeError(msg)

        monkeypatch.setitem(sys.modules, name, None)  # type: ignore[arg-type]

    async def test_mongodb_missing_dep_raises_runtime_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MONGODB_ATLAS_URI", "mongodb+srv://demo")
        self._hide_module(monkeypatch, "langchain_mongodb")
        self._hide_module(monkeypatch, "pymongo")
        backend = MongoDBBackend(
            kb_name="kb",
            kb_path=tmp_path,
            backend_config={"database": "d", "collection": "c"},
        )
        with pytest.raises(RuntimeError, match="langchain-mongodb"):
            backend._build_vector_store()

    async def test_astra_missing_dep_raises_runtime_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://x")
        monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "tok")
        self._hide_module(monkeypatch, "langchain_astradb")
        backend = AstraBackend(kb_name="kb", kb_path=tmp_path, backend_config={"collection_name": "c"})
        with pytest.raises(RuntimeError, match="langchain-astradb"):
            backend._build_vector_store()

    async def test_postgres_missing_dep_raises_runtime_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv("POSTGRES_CONNECTION_URL", "postgresql://demo")
        self._hide_module(monkeypatch, "langchain_postgres")
        backend = PostgresBackend(kb_name="kb", kb_path=tmp_path, backend_config={"collection_name": "c"})
        with pytest.raises(RuntimeError, match="langchain-postgres"):
            backend._build_vector_store()
