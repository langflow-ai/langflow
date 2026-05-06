"""service-init parity test fixtures.

Provides a phase-local ``tmp_config_dir`` that redirects
``LANGFLOW_CONFIG_DIR`` + ``LANGFLOW_DATABASE_URL`` into a per-test tmp
directory so hash-file writes do not leak across tests, plus pointers to the
synthetic starter folders used by ``test_svc01_starter_hash_cache.py``.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import anyio
import pytest
from langflow.services.deps import get_settings_service

_FIXTURES_ROOT = Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """Redirect ``LANGFLOW_CONFIG_DIR`` + DB to a per-test temp directory.

    Mirrors the shape of ``src/backend/tests/performance/test_server_init.py``
    but scopes to ``LANGFLOW_CONFIG_DIR`` as well so that hash-file writes
    land under an isolated directory. The fixture yields the config dir as a
    ``Path`` for tests that want to inspect ``<config_dir>/starter_projects.hash``
    directly.
    """
    settings_service = get_settings_service()
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test_.db"
    test_db_url = f"sqlite:///{db_path}"

    original_config = os.getenv("LANGFLOW_CONFIG_DIR")
    original_db = os.getenv("LANGFLOW_DATABASE_URL")
    original_force = os.getenv("LANGFLOW_FORCE_STARTER_RESYNC")

    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", test_db_url)
    # Ensure force-resync is not inherited from the host environment.
    monkeypatch.delenv("LANGFLOW_FORCE_STARTER_RESYNC", raising=False)

    settings_service.set("config_dir", str(config_dir))
    settings_service.set("database_url", test_db_url)

    yield config_dir

    # Restore settings-service values (monkeypatch handles env vars).
    if original_config is not None:
        settings_service.set("config_dir", original_config)
    if original_db is not None:
        settings_service.set("database_url", original_db)
    # Re-exporting the force-resync env var is not needed -- monkeypatch
    # handles that automatically when the fixture tears down, but we
    # reference ``original_force`` here to document the captured state.
    _ = original_force


@pytest.fixture
def seeded_hash_file(tmp_config_dir):
    """Factory: copy a fixture hash file into ``tmp_config_dir / starter_projects.hash``.

    Usage::

        def test_something(seeded_hash_file):
            seeded_hash_file("seeded_hash_mismatch.txt")
    """

    def _copy(fixture_name: str) -> Path:
        src = _FIXTURES_ROOT / fixture_name
        dst = tmp_config_dir / "starter_projects.hash"
        shutil.copyfile(src, dst)
        return dst

    return _copy


@pytest.fixture
def starter_folder_minimal() -> anyio.Path:
    """Return an ``anyio.Path`` pointing at the phase-local minimal starter folder."""
    return anyio.Path(_FIXTURES_ROOT / "starter_minimal")


@pytest.fixture
def starter_folder_mutated() -> anyio.Path:
    """Return an ``anyio.Path`` pointing at the one-byte-mutated starter folder."""
    return anyio.Path(_FIXTURES_ROOT / "starter_mutated")
