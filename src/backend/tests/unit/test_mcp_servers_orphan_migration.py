"""Tests for migrate_orphaned_mcp_servers_config in langflow.services.utils.

Verifies that MCP server config files written under a previous default
superuser's UUID are picked up and migrated to the new default superuser
when the database is reset but the config directory is preserved
(typical of containerized deployments without a persisted DB volume).
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from pathlib import Path
from langflow.services.database.models.file.model import File as UserFile
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.utils import migrate_orphaned_mcp_servers_config
from sqlmodel import select


@pytest.fixture
async def initialized_services(monkeypatch, tmp_path):
    """Initialize DB + services with an isolated config dir."""
    from langflow.services.utils import initialize_services, teardown_services
    from lfx.services.manager import get_service_manager

    db_path = tmp_path / "test.db"
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")

    get_service_manager().factories.clear()
    get_service_manager().services.clear()

    await initialize_services()

    yield config_dir

    await teardown_services()


def _write_orphan(config_dir: Path, payload: dict, *, mtime_offset: float = 0.0) -> Path:
    """Create an orphaned _mcp_servers_{uuid}.json file in a UUID-named folder."""
    orphan_id = uuid4()
    orphan_dir = config_dir / str(orphan_id)
    orphan_dir.mkdir(parents=True, exist_ok=True)
    orphan_path = orphan_dir / f"_mcp_servers_{orphan_id}.json"
    orphan_path.write_text(json.dumps(payload))
    if mtime_offset:
        stat = orphan_path.stat()
        os.utime(orphan_path, (stat.st_atime + mtime_offset, stat.st_mtime + mtime_offset))
    return orphan_path


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_migrate_orphaned_mcp_servers_config_recovers_previous_user_config(
    initialized_services,
):
    """A single orphaned file is migrated to the current default superuser."""
    config_dir: Path = initialized_services
    expected_payload = {"mcpServers": {"my-server": {"command": "uvx", "args": ["mcp-proxy"]}}}
    orphan_path = _write_orphan(config_dir, expected_payload)

    settings = get_settings_service()

    async with session_scope() as session:
        from langflow.services.database.models.user.model import User
        from lfx.services.settings.constants import DEFAULT_SUPERUSER

        user = (await session.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).first()
        assert user is not None, "default superuser should exist after initialize_services"

        # Simulate the fresh-DB scenario: the user has no MCP config row yet.
        stmt = select(UserFile).where(UserFile.user_id == user.id).where(UserFile.name == f"_mcp_servers_{user.id}")
        assert (await session.exec(stmt)).first() is None

        migrated = await migrate_orphaned_mcp_servers_config(session, settings, user)
        assert migrated is True

        # DB record should exist and point at the new user-specific path.
        stmt = select(UserFile).where(UserFile.user_id == user.id).where(UserFile.name == f"_mcp_servers_{user.id}")
        new_record = (await session.exec(stmt)).first()
        assert new_record is not None
        assert new_record.path == f"{user.id}/_mcp_servers_{user.id}.json"

    # File should live under the new user's folder with the same contents.
    target = config_dir / str(user.id) / f"_mcp_servers_{user.id}.json"
    assert target.exists()
    assert json.loads(target.read_text()) == expected_payload
    # Orphan source is left intact (best-effort copy, not destructive move).
    assert orphan_path.exists()


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_migrate_orphaned_mcp_servers_config_skips_when_multiple_orphans(
    initialized_services,
):
    """With multiple orphan candidates we refuse to guess and leave state untouched.

    MCP server entries can contain env/headers auth material, so importing an
    unrelated user's config would be a security hazard. Operators must resolve
    the ambiguity manually.
    """
    config_dir: Path = initialized_services

    old_payload = {"mcpServers": {"old": {}}}
    new_payload = {"mcpServers": {"new": {}}}

    old_path = _write_orphan(config_dir, old_payload, mtime_offset=-3600)
    new_path = _write_orphan(config_dir, new_payload)

    settings = get_settings_service()

    async with session_scope() as session:
        from langflow.services.database.models.user.model import User
        from lfx.services.settings.constants import DEFAULT_SUPERUSER

        user = (await session.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).first()
        migrated = await migrate_orphaned_mcp_servers_config(session, settings, user)
        assert migrated is False

        stmt = select(UserFile).where(UserFile.user_id == user.id).where(UserFile.name == f"_mcp_servers_{user.id}")
        assert (await session.exec(stmt)).first() is None

    target = config_dir / str(user.id) / f"_mcp_servers_{user.id}.json"
    assert not target.exists()
    # Both orphans are preserved on disk for manual recovery.
    assert json.loads(old_path.read_text()) == old_payload
    assert json.loads(new_path.read_text()) == new_payload


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_migrate_orphaned_mcp_servers_config_no_orphans_is_noop(
    initialized_services,
):
    """With no orphaned files the function returns False and does not touch the DB."""
    config_dir: Path = initialized_services
    # No UUID-named subdirectories should exist.
    from uuid import UUID

    def _is_uuid_dir(p: Path) -> bool:
        if not p.is_dir():
            return False
        try:
            UUID(p.name)
        except ValueError:
            return False
        return True

    assert not [p for p in config_dir.iterdir() if _is_uuid_dir(p)]

    settings = get_settings_service()

    async with session_scope() as session:
        from langflow.services.database.models.user.model import User
        from lfx.services.settings.constants import DEFAULT_SUPERUSER

        user = (await session.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).first()
        migrated = await migrate_orphaned_mcp_servers_config(session, settings, user)
        assert migrated is False

        stmt = select(UserFile).where(UserFile.user_id == user.id).where(UserFile.name == f"_mcp_servers_{user.id}")
        assert (await session.exec(stmt)).first() is None


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_migrate_orphaned_mcp_servers_config_self_heals_missing_db_row(
    initialized_services,
):
    """Re-register missing DB rows when the on-disk file already exists.

    If the user's file is on disk but the DB row is missing, the migration
    should recreate the row instead of leaving the config invisible. This
    covers recovery from a previous migration attempt that wrote the file
    but crashed before committing the DB row.
    """
    config_dir: Path = initialized_services
    settings = get_settings_service()

    async with session_scope() as session:
        from langflow.services.database.models.user.model import User
        from lfx.services.settings.constants import DEFAULT_SUPERUSER

        user = (await session.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).first()

        # Simulate a file-exists / DB-row-missing state.
        existing_dir = config_dir / str(user.id)
        existing_dir.mkdir(parents=True, exist_ok=True)
        existing_payload = {"mcpServers": {"keep-me": {}}}
        existing_path = existing_dir / f"_mcp_servers_{user.id}.json"
        existing_path.write_text(json.dumps(existing_payload))

        migrated = await migrate_orphaned_mcp_servers_config(session, settings, user)
        assert migrated is True

        stmt = select(UserFile).where(UserFile.user_id == user.id).where(UserFile.name == f"_mcp_servers_{user.id}")
        row = (await session.exec(stmt)).first()
        assert row is not None
        assert row.path == f"{user.id}/_mcp_servers_{user.id}.json"
        assert row.size == existing_path.stat().st_size

    # File contents are untouched.
    assert json.loads(existing_path.read_text()) == existing_payload


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_migrate_orphaned_mcp_servers_config_skips_when_row_already_present(
    initialized_services,
):
    """When the DB row already exists, do nothing — avoids double-registration."""
    config_dir: Path = initialized_services
    _write_orphan(config_dir, {"mcpServers": {"orphan": {}}})

    settings = get_settings_service()

    async with session_scope() as session:
        from langflow.services.database.models.user.model import User
        from lfx.services.settings.constants import DEFAULT_SUPERUSER

        user = (await session.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).first()

        # Pre-register an MCP file row to simulate an already-migrated user.
        session.add(
            UserFile(
                user_id=user.id,
                name=f"_mcp_servers_{user.id}",
                path=f"{user.id}/_mcp_servers_{user.id}.json",
                size=0,
            )
        )
        await session.commit()

        migrated = await migrate_orphaned_mcp_servers_config(session, settings, user)
        assert migrated is False
