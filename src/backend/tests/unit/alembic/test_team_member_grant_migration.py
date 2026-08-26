"""Upgrade/downgrade and legacy-preservation tests for Team grant provenance."""

from __future__ import annotations

import importlib
import types
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa

_MIGRATION = importlib.import_module("langflow.alembic.versions.b8e1d4f6a2c9_add_team_member_grants")


def _database():
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
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


def _run(engine, action: str) -> None:
    with engine.begin() as connection:
        original_op = _MIGRATION.op
        try:
            _MIGRATION.op = types.SimpleNamespace(
                get_bind=lambda: connection,
                create_table=lambda *args, **kwargs: sa.Table(args[0], sa.MetaData(), *args[1:], **kwargs).create(
                    connection
                ),
                create_index=lambda name, table, columns, **kwargs: sa.Index(
                    name,
                    *[sa.Table(table, sa.MetaData(), autoload_with=connection).c[column] for column in columns],
                    **kwargs,
                ).create(connection),
                drop_index=lambda name, _table_name=None: sa.Index(name).drop(connection),
                drop_table=lambda name: sa.Table(name, sa.MetaData(), autoload_with=connection).drop(connection),
            )
            getattr(_MIGRATION, action)()
        finally:
            _MIGRATION.op = original_op


def test_upgrade_backfills_manual_and_unresolved_legacy_without_name_linking() -> None:
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

    _run(engine, "upgrade")
    _run(engine, "upgrade")

    grant = sa.Table("authz_team_member_grant", sa.MetaData(), autoload_with=engine)
    with engine.connect() as connection:
        rows = connection.execute(sa.select(grant).order_by(grant.c.membership_id)).mappings().all()
    by_membership = {row["membership_id"]: row for row in rows}
    assert by_membership[manual_id]["source_kind"] == "manual"
    assert by_membership[legacy_id]["source_kind"] == "legacy"
    assert by_membership[legacy_id]["legacy_source"] == "engineering-group-name"
    assert by_membership[legacy_id]["provider_id"] is None
    assert by_membership[legacy_id]["external_group_id"] is None

    _run(engine, "downgrade")
    assert "authz_team_member_grant" not in sa.inspect(engine).get_table_names()
