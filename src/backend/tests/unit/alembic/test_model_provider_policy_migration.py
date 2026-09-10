"""Schema contract for the install-wide model-provider policy singleton."""

from __future__ import annotations

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

_MIGRATION = importlib.import_module("langflow.alembic.versions.e8f1a2b3c4d5_add_model_provider_policy")


def test_model_provider_policy_migration_upgrades_and_downgrades_sqlite(monkeypatch):
    engine = sa.create_engine("sqlite://")

    with engine.begin() as connection:
        monkeypatch.setattr(_MIGRATION, "op", Operations(MigrationContext.configure(connection)))

        _MIGRATION.upgrade()
        _MIGRATION.upgrade()

        inspector = sa.inspect(connection)
        columns = {column["name"]: column for column in inspector.get_columns(_MIGRATION.TABLE_NAME)}
        primary_key = inspector.get_pk_constraint(_MIGRATION.TABLE_NAME)

        assert _MIGRATION.down_revision == "cp03a2b3c4d5"  # pragma: allowlist secret
        assert set(columns) == {"id", "approved_provider_ids", "version"}
        assert all(column["nullable"] is False for column in columns.values())
        assert primary_key["constrained_columns"] == ["id"]

        table = sa.Table(_MIGRATION.TABLE_NAME, sa.MetaData(), autoload_with=connection)
        seeded = connection.execute(sa.select(table)).mappings().one()
        assert seeded == {"id": 1, "approved_provider_ids": [], "version": 0}

        with pytest.raises(IntegrityError):
            connection.execute(
                table.insert(),
                {"id": 2, "approved_provider_ids": ["openai"], "version": 1},
            )

        _MIGRATION.downgrade()
        assert not sa.inspect(connection).has_table(_MIGRATION.TABLE_NAME)
