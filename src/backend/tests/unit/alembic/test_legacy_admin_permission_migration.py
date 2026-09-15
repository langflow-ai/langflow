"""Compatibility tests for legacy administration permission normalization."""

from __future__ import annotations

import importlib
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION = importlib.import_module("langflow.alembic.versions.c9f2e5a7b1d4_normalize_legacy_admin_permissions")


def test_upgrade_normalizes_only_legacy_administration_wildcards(monkeypatch) -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    role = sa.Table(
        "authz_role",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
    )
    metadata.create_all(engine)
    legacy_id = uuid4()
    current_id = uuid4()

    with engine.begin() as connection:
        connection.execute(
            role.insert(),
            [
                {
                    "id": legacy_id,
                    "permissions": ["user:*", "flow:*", "team:*", "user:manage", "role:*"],
                },
                {"id": current_id, "permissions": ["flow:*", "team:manage"]},
            ],
        )
        monkeypatch.setattr(_MIGRATION, "op", Operations(MigrationContext.configure(connection)))

        _MIGRATION.upgrade()
        rows = {
            row["id"]: row["permissions"]
            for row in connection.execute(sa.select(role.c.id, role.c.permissions)).mappings()
        }

    assert rows[legacy_id] == ["user:manage", "flow:*", "team:manage", "role:manage"]
    assert rows[current_id] == ["flow:*", "team:manage"]
