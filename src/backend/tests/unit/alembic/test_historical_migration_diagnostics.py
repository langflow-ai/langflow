from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock

import sqlalchemy as sa


def test_sqlite_datetime_noop_is_debug_only(monkeypatch):
    migration = import_module("langflow.alembic.versions.79e675cb6752_change_datetime_type")
    logger = MagicMock()
    monkeypatch.setattr(migration, "logger", logger)

    migration._log_unhandled_column_type(
        conn=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
        table_name="variable",
        column_name="created_at",
        column_type=sa.DateTime(),
    )

    logger.debug.assert_called_once()
    logger.warning.assert_not_called()


def test_unexpected_historical_column_type_remains_warning(monkeypatch):
    migration = import_module("langflow.alembic.versions.79e675cb6752_change_datetime_type")
    logger = MagicMock()
    monkeypatch.setattr(migration, "logger", logger)

    migration._log_unhandled_column_type(
        conn=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
        table_name="variable",
        column_name="created_at",
        column_type=sa.String(),
    )

    logger.warning.assert_called_once()
    logger.debug.assert_not_called()
