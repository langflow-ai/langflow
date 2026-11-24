from __future__ import annotations

import re
from contextlib import nullcontext
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from langflow.services.database import service as database_service_module
from langflow.services.database.service import DatabaseService

CURRENT_REVISION = "f7a9c2d4e6b8"  # pragma: allowlist secret
TARGET_REVISION = "8d9e0f1a2b3c"  # pragma: allowlist secret


def _service(monkeypatch, *, current_revisions: set[str]) -> DatabaseService:
    service = object.__new__(DatabaseService)
    service.database_url = "sqlite+aiosqlite:////configured/production.db"
    service.script_location = Path("/installed/langflow/alembic")
    service._open_alembic_log_buffer = lambda: nullcontext(StringIO())
    monkeypatch.setattr(service, "_current_alembic_revisions", lambda: current_revisions)
    return service


def test_explicit_downgrade_uses_configured_database_and_script_location(monkeypatch):
    service = _service(monkeypatch, current_revisions={CURRENT_REVISION})
    downgrade = Mock()
    monkeypatch.setattr(database_service_module.command, "downgrade", downgrade)

    service._run_migration_downgrade(
        expected_current_revision=CURRENT_REVISION,
        target_revision=TARGET_REVISION,
    )

    alembic_cfg, target = downgrade.call_args.args
    assert target == TARGET_REVISION
    assert alembic_cfg.get_main_option("script_location") == "/installed/langflow/alembic"
    assert alembic_cfg.get_main_option("sqlalchemy.url") == "sqlite+aiosqlite:////configured/production.db"


def test_current_alembic_revisions_reads_a_sanitized_file_backed_sqlite_database(tmp_path):
    database_path = tmp_path / "revisions.db"
    sync_url = f"sqlite:///{database_path}"
    engine = sa.create_engine(sync_url)
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            connection.execute(
                sa.text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
                {"revision": CURRENT_REVISION},
            )
    finally:
        engine.dispose()

    service = object.__new__(DatabaseService)
    service.database_url = f"sqlite+aiosqlite:///{database_path}"

    assert service._current_alembic_revisions() == {CURRENT_REVISION}


@pytest.mark.parametrize(
    ("current_revisions", "expected_found"),
    [
        ({"later_revision"}, "later_revision"),
        ({CURRENT_REVISION, "other_head"}, f"{CURRENT_REVISION}, other_head"),
        (set(), "none"),
    ],
    ids=["later-revision", "multiple-heads", "no-revision"],
)
def test_explicit_downgrade_refuses_an_unexpected_database_revision(
    monkeypatch,
    current_revisions,
    expected_found,
):
    service = _service(monkeypatch, current_revisions=current_revisions)
    downgrade = Mock()
    monkeypatch.setattr(database_service_module.command, "downgrade", downgrade)

    expected_message = rf"expected current revision {CURRENT_REVISION}, found {re.escape(expected_found)}"
    with pytest.raises(RuntimeError, match=expected_message):
        service._run_migration_downgrade(
            expected_current_revision=CURRENT_REVISION,
            target_revision=TARGET_REVISION,
        )

    downgrade.assert_not_called()
