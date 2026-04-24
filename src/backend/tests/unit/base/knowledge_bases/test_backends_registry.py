"""Unit tests for the vector-store backend registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
from lfx.base.knowledge_bases.backends import (
    BackendType,
    BaseVectorStoreBackend,
    ChromaBackend,
    VectorStoreBackend,
    create_backend,
    get_backend_class,
    register_backend,
    registered_backends,
)
from lfx.base.knowledge_bases.backends.registry import _resolve_backend_type


class _DummyBackend(BaseVectorStoreBackend):
    """Minimal in-memory backend used for registry tests."""

    backend_type = BackendType.MONGODB  # reuse a reserved identifier

    def _build_vector_store(self):  # pragma: no cover — not exercised here
        raise NotImplementedError


class TestBackendRegistry:
    """The registry is the swap point for future DB backends (MongoDB, Astra, Postgres)."""

    def test_chroma_registered_by_default(self):
        assert BackendType.CHROMA in registered_backends()
        assert get_backend_class(BackendType.CHROMA) is ChromaBackend

    def test_registered_backends_returns_stable_ordering(self):
        backends = registered_backends()
        assert backends == tuple(sorted(backends, key=lambda bt: bt.value))

    def test_create_backend_returns_chroma_instance(self, tmp_path: Path):
        backend = create_backend(
            BackendType.CHROMA,
            kb_name="test_kb",
            kb_path=tmp_path,
        )
        assert isinstance(backend, ChromaBackend)
        assert isinstance(backend, VectorStoreBackend)  # Protocol runtime-check
        assert backend.kb_name == "test_kb"
        assert backend.kb_path == tmp_path

    def test_create_backend_accepts_string_identifier(self, tmp_path: Path):
        backend = create_backend("chroma", kb_name="kb2", kb_path=tmp_path)
        assert isinstance(backend, ChromaBackend)

    def test_get_backend_class_rejects_unregistered_enum_value(self):
        """Unregistered enum values fail loudly.

        Phase 4 registered astra/mongodb/postgres. If a future enum
        member lands without a matching ``register_backend`` call,
        the registry must fail loudly rather than silently degrade.
        """
        # Patch the registry to simulate an identifier that's been added
        # to the enum but never wired up.
        from unittest.mock import patch

        from lfx.base.knowledge_bases.backends import registry

        with patch.dict(registry._BACKEND_REGISTRY, clear=False) as _:
            registry._BACKEND_REGISTRY.pop(BackendType.ASTRA, None)
            try:
                with pytest.raises(ValueError, match="not registered"):
                    get_backend_class(BackendType.ASTRA)
            finally:
                # Re-register for the rest of the suite.
                from lfx.base.knowledge_bases.backends import AstraBackend

                registry._BACKEND_REGISTRY[BackendType.ASTRA] = AstraBackend

    def test_resolve_backend_type_rejects_garbage_strings(self):
        with pytest.raises(ValueError, match="Unknown vector-store backend"):
            _resolve_backend_type("does-not-exist")

    def test_register_backend_is_idempotent(self):
        # Re-registering the same class is a no-op.
        register_backend(BackendType.CHROMA, ChromaBackend)
        assert get_backend_class(BackendType.CHROMA) is ChromaBackend

    def test_register_backend_rejects_conflicting_registration(self):
        # Guards against accidental collisions when two modules both try to
        # register under the same identifier.
        with pytest.raises(ValueError, match="already registered"):
            register_backend(BackendType.CHROMA, _DummyBackend)
