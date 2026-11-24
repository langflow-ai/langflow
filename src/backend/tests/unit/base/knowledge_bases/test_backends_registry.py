"""Unit tests for the vector-store backend registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
from lfx.base.knowledge_bases.backends import (
    BackendType,
    BaseVectorStoreBackend,
    SQLiteBackend,
    create_backend,
    get_backend_class,
    register_backend,
    registered_backends,
)
from lfx.base.knowledge_bases.backends.registry import _resolve_backend_type


class _DummyBackend(BaseVectorStoreBackend):
    """Minimal in-memory backend used for registry tests."""

    # ``MONGODB`` is one of the stubbed-but-not-registered backends, so the
    # registry has a free slot under that key without colliding with anything
    # the framework registers on import.
    backend_type = BackendType.MONGODB

    def _build_vector_store(self):  # pragma: no cover — not exercised here
        raise NotImplementedError


class TestBackendRegistry:
    """The registry is the swap point for the supported DB backends.

    SQLite, OpenSearch, and Postgres (pgvector) are registered. The Astra /
    MongoDB backends ship as stubs that exist for type and enum compatibility
    but are intentionally not in the registry, so ``create_backend('astra')``
    (etc.) raises.
    """

    def test_sqlite_registered_by_default(self):
        assert BackendType.SQLITE in registered_backends()
        assert get_backend_class(BackendType.SQLITE) is SQLiteBackend

    def test_opensearch_registered_by_default(self):
        # OpenSearch is the second supported backend in this phase.
        assert BackendType.OPENSEARCH in registered_backends()

    def test_postgres_registered_by_default(self):
        # pgVector is environment-driven and registered unconditionally.
        assert BackendType.POSTGRES in registered_backends()

    def test_stubbed_backends_are_not_registered(self):
        registered = registered_backends()
        for stubbed in (BackendType.ASTRA, BackendType.MONGODB):
            assert stubbed not in registered, f"{stubbed.value} is stubbed in this phase and must not be registered"
            with pytest.raises(ValueError, match="not registered"):
                get_backend_class(stubbed)

    def test_registered_backends_returns_stable_ordering(self):
        backends = registered_backends()
        assert backends == tuple(sorted(backends, key=lambda bt: bt.value))

    def test_create_backend_returns_sqlite_instance(self, tmp_path: Path):
        from uuid import uuid4

        from lfx.base.knowledge_bases.backends.sqlite import SQLiteStorageContext

        context = SQLiteStorageContext(tmp_path, uuid4(), uuid4())
        backend = create_backend("sqlite", kb_name="test_kb", storage_context=context)
        assert isinstance(backend, SQLiteBackend)
        assert backend.kb_name == "test_kb"

    def test_resolve_backend_type_rejects_garbage_strings(self):
        with pytest.raises(ValueError, match="Unknown vector-store backend"):
            _resolve_backend_type("does-not-exist")

    def test_register_backend_is_idempotent(self):
        # Re-registering the same class is a no-op.
        register_backend(BackendType.SQLITE, SQLiteBackend)
        assert get_backend_class(BackendType.SQLITE) is SQLiteBackend

    def test_register_backend_rejects_conflicting_registration(self):
        # Guards against accidental collisions when two modules both try to
        # register under the same identifier.
        with pytest.raises(ValueError, match="already registered"):
            register_backend(BackendType.SQLITE, _DummyBackend)
