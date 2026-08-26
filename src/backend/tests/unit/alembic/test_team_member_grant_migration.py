"""Upgrade/downgrade and legacy-preservation tests for Team grant provenance."""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION = importlib.import_module("langflow.alembic.versions.b8e1d4f6a2c9_add_team_member_grants")


def _database():
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    sa.Table(
        "user",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
    )
    membership = sa.Table(
        "authz_team_member",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(engine)
    return engine, membership


def test_upgrade_backfills_manual_and_unresolved_legacy_without_name_linking(monkeypatch) -> None:
    engine, membership = _database()
    manual_id = uuid4()
    legacy_id = uuid4()
    timestamp = datetime(2026, 8, 26, tzinfo=timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            membership.insert(),
            [
                {
                    "id": manual_id,
                    "team_id": uuid4(),
                    "user_id": uuid4(),
                    "source": "manual",
                    "created_at": timestamp,
                },
                {
                    "id": legacy_id,
                    "team_id": uuid4(),
                    "user_id": uuid4(),
                    "source": "engineering-group-name",
                    "created_at": timestamp,
                },
            ],
        )

    with engine.begin() as connection:
        monkeypatch.setattr(_MIGRATION, "op", Operations(MigrationContext.configure(connection)))
        _MIGRATION.upgrade()
        _MIGRATION.upgrade()
        grant = sa.Table("authz_team_member_grant", sa.MetaData(), autoload_with=connection)
        rows = connection.execute(sa.select(grant).order_by(grant.c.membership_id)).mappings().all()
        by_membership = {UUID(str(row["membership_id"])): row for row in rows}
        assert by_membership[manual_id]["source_kind"] == "manual"
        assert by_membership[legacy_id]["source_kind"] == "legacy"
        assert by_membership[legacy_id]["legacy_source"] == "engineering-group-name"
        assert by_membership[legacy_id]["provider_id"] is None
        assert by_membership[legacy_id]["external_group_id"] is None

        _MIGRATION.downgrade()
        assert "authz_team_member_grant" not in sa.inspect(connection).get_table_names()
