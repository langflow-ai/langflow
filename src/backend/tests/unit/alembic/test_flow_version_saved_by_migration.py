"""Versions saved before ``saved_by_user_id`` existed keep their author and their owner."""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import command

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

BEFORE = "e3a7b9c1d5f2"  # pragma: allowlist secret


def test_existing_versions_are_attributed_to_whoever_saved_them(db_url):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, BEFORE)
    engine = sa.create_engine(_engine_url(db_url))
    owner, flow, saved, checkpoint = uuid4(), uuid4(), uuid4(), uuid4()

    def uuid(name, value):
        return sa.bindparam(name, value, type_=sa.Uuid())

    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    'INSERT INTO "user" (id, username, password, is_active, is_superuser, create_at, updated_at) '
                    "VALUES (:id, 'owner', 'x', true, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ).bindparams(uuid("id", owner))
            )
            conn.execute(
                sa.text(
                    "INSERT INTO flow (id, name, user_id, updated_at) VALUES (:id, 'f', :owner, CURRENT_TIMESTAMP)"
                ).bindparams(uuid("id", flow), uuid("owner", owner))
            )
            for version_id, number in ((saved, 1), (checkpoint, None)):
                conn.execute(
                    sa.text(
                        "INSERT INTO flow_version (id, flow_id, user_id, data, version_number, created_at, view_only) "
                        "VALUES (:id, :flow, :owner, '{}', :number, CURRENT_TIMESTAMP, false)"
                    ).bindparams(uuid("id", version_id), uuid("flow", flow), uuid("owner", owner), number=number)
                )

        command.upgrade(config, "head")

        with engine.connect() as conn:
            rows = conn.execute(
                sa.text("SELECT id, user_id, saved_by_user_id FROM flow_version").columns(
                    sa.column("id", sa.Uuid()),
                    sa.column("user_id", sa.Uuid()),
                    sa.column("saved_by_user_id", sa.Uuid()),
                )
            ).all()
        by_id = {row.id: row for row in rows}
        assert by_id[saved].saved_by_user_id == owner
        assert by_id[saved].user_id == owner
        # System checkpoints were saved by no one.
        assert by_id[checkpoint].saved_by_user_id is None
    finally:
        engine.dispose()
