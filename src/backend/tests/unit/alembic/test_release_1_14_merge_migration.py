"""Upgrade both published release histories without losing completed OAuth grants."""

from uuid import uuid4

import pytest
from alembic import command
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from .test_connection_oauth_migration import _grant_payload, _seed_legacy_grant
from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401


@pytest.mark.parametrize(
    "starting_revision",
    ["e4f6a8b2c1d3", "c6a81d3e9502"],  # pragma: allowlist secret
    ids=["release-1.13.1", "release-1.14.0"],
)
def test_upgrade_from_published_release_preserves_oauth_grant(db_url, starting_revision):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, "e5a7c9b1d3f2")  # pragma: allowlist secret
    engine = create_engine(_engine_url(db_url))
    owner_id = str(uuid4())
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    'INSERT INTO "user" (id, username, password, is_active, is_superuser, create_at, updated_at) '
                    "VALUES (:id, :username, 'x', true, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"id": owner_id, "username": f"release-upgrade-{owner_id}"},
            )
            _seed_legacy_grant(
                connection,
                owner_id,
                str(uuid4()),
                "retained-grant",
                "ready",
                "oauth-failed",
                "pending-app",
                _grant_payload("completed-app"),
                None,
            )

        command.upgrade(config, starting_revision)
        command.upgrade(config, "head")
        command.check(config)

        with engine.connect() as connection:
            stored = connection.execute(
                text("SELECT registration_id, completed_registration_id FROM connection_oauth")
            ).one()
            assert tuple(stored) == ("pending-app", "completed-app")
            assert "ix_connection_oauth_completed_registration_id" in {
                index["name"] for index in inspect(connection).get_indexes("connection_oauth")
            }
            assert MigrationContext.configure(connection).get_current_heads() == (
                ScriptDirectory.from_config(config).get_current_head(),
            )
    finally:
        engine.dispose()
