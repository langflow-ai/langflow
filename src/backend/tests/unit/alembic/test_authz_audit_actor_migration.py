"""Schema contract for first-class authorization-audit actors."""

from __future__ import annotations

import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION = importlib.import_module("langflow.alembic.versions.a6c4e2f8b1d3_add_authz_audit_actor_identity")


def test_actor_migration_upgrades_and_downgrades_sqlite(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "authz_audit_log",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        _MIGRATION.upgrade()
        inspector = sa.inspect(connection)
        column_rows = {column["name"]: column for column in inspector.get_columns("authz_audit_log")}
        indexes = {index["name"]: tuple(index["column_names"]) for index in inspector.get_indexes("authz_audit_log")}
        foreign_keys = inspector.get_foreign_keys("authz_audit_log")

        assert _MIGRATION.down_revision == "d19e7b3c5a42"  # pragma: allowlist secret
        assert {"actor_type", "actor_id"} <= column_rows.keys()
        assert column_rows["actor_type"]["nullable"] is True
        assert column_rows["actor_id"]["nullable"] is True
        assert indexes["ix_authz_audit_log_actor_timestamp"] == ("actor_id", "timestamp")
        assert indexes["ix_authz_audit_log_actor_type_timestamp"] == ("actor_type", "timestamp")
        assert all("actor_id" not in (foreign_key.get("constrained_columns") or []) for foreign_key in foreign_keys)

        _MIGRATION.downgrade()
        remaining = {column["name"] for column in sa.inspect(connection).get_columns("authz_audit_log")}
        assert "actor_type" not in remaining
        assert "actor_id" not in remaining
