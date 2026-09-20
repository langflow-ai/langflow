"""SQLite contract tests for the SSO identity-details migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION_PATH = Path(__file__).parents[3] / "base/langflow/alembic/versions/c6d8e0f2a4b7_add_sso_identity_details.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("sso_identity_details_migration", _MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_adds_nullable_identity_details_and_preserves_legacy_rows(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")

    with engine.begin() as connection:
        metadata = sa.MetaData()
        profile = sa.Table(
            "sso_user_profile",
            metadata,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(), nullable=True),
        )
        metadata.create_all(connection)
        connection.execute(profile.insert().values(id=1, email="legacy@example.com"))

        monkeypatch.setattr(
            migration,
            "op",
            Operations(MigrationContext.configure(connection)),
        )
        migration.upgrade()
        migration.upgrade()

        columns = {column["name"]: column for column in sa.inspect(connection).get_columns("sso_user_profile")}
        assert {"first_name", "last_name", "picture"} <= columns.keys()
        assert all(columns[name]["nullable"] for name in ("first_name", "last_name", "picture"))

        upgraded = sa.Table("sso_user_profile", sa.MetaData(), autoload_with=connection)
        row = connection.execute(sa.select(upgraded)).mappings().one()
        assert row["email"] == "legacy@example.com"
        assert row["first_name"] is None
        assert row["last_name"] is None
        assert row["picture"] is None

        migration.downgrade()
        migration.downgrade()
        assert {column["name"] for column in sa.inspect(connection).get_columns("sso_user_profile")} == {"id", "email"}
