from __future__ import annotations

from contextlib import nullcontext
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

import pytest
from langflow.services.database import service as database_service_module
from langflow.services.database.service import DatabaseService

CURRENT_REVISION = "f7a9c2d4e6b8"  # pragma: allowlist secret
TARGET_REVISION = "8d9e0f1a2b3c"  # pragma: allowlist secret


def _service(monkeypatch, *, current_revisions: set[str]) -> DatabaseService:
    service = object.__new__(DatabaseService)
    service.database_url = "sqlite:////configured/production.db"
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
    assert alembic_cfg.get_main_option("sqlalchemy.url") == "sqlite:////configured/production.db"


def test_explicit_downgrade_refuses_an_unexpected_database_revision(monkeypatch):
    service = _service(monkeypatch, current_revisions={"later_revision"})
    downgrade = Mock()
    monkeypatch.setattr(database_service_module.command, "downgrade", downgrade)

    with pytest.raises(RuntimeError, match=rf"expected current revision {CURRENT_REVISION}, found later_revision"):
        service._run_migration_downgrade(
            expected_current_revision=CURRENT_REVISION,
            target_revision=TARGET_REVISION,
        )

    downgrade.assert_not_called()
