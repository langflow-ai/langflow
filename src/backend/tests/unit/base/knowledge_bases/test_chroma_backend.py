"""Legacy routes must fail before opening data or initializing a provider SDK."""

from __future__ import annotations

import pytest
from lfx.base.knowledge_bases.backends import BackendType, create_backend, get_backend_class, registered_backends
from lfx.base.knowledge_bases.backends.chroma import (
    ChromaBackend,
    ChromaCloudBackend,
    ChromaLocalBackend,
    ChromaMigrationRequiredError,
    build_default_chroma_backend,
)
from lfx.base.knowledge_bases.backends.registry import register_backend


@pytest.mark.parametrize("mode", ["local", "cloud"])
def test_legacy_routing_requires_migration(mode, tmp_path):
    source = tmp_path / "source"
    with pytest.raises(ChromaMigrationRequiredError, match="requires migration"):
        create_backend("chroma", "old", source, backend_config={"mode": mode})
    assert not source.exists()


@pytest.mark.parametrize(
    "backend", [ChromaBackend, ChromaLocalBackend, ChromaCloudBackend, build_default_chroma_backend]
)
def test_historical_entry_points_cannot_open_a_store(backend, tmp_path):
    with pytest.raises(ChromaMigrationRequiredError, match="Original data is retained"):
        backend(kb_name="old", kb_path=tmp_path / "source")
    assert not list(tmp_path.iterdir())


def test_chroma_cannot_be_registered_or_selected():
    assert BackendType.CHROMA not in registered_backends()
    with pytest.raises(ChromaMigrationRequiredError):
        get_backend_class("chroma")
    with pytest.raises(ChromaMigrationRequiredError):
        register_backend(BackendType.CHROMA, ChromaBackend)
