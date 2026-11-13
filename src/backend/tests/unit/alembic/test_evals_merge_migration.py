"""Preserve data when joining the Evals and release migration histories."""

from uuid import uuid4

import pytest
from alembic import command
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401


@pytest.mark.parametrize(
    "starting_revision",
    ["a1d7e3c5b9f2", "f2d6b8c4a901", "d7e9f1a3b5c7", "9c4b7e2a6d10"],  # pragma: allowlist secret
    ids=["evals", "release", "evals-merged", "release-upgrade-reports"],
)
def test_evals_and_release_upgrade_preserves_data(db_url, starting_revision):  # noqa: F811
    """Both existing heads must upgrade to one head without losing stored data."""
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, starting_revision)
    engine = create_engine(_engine_url(db_url))
    owner_id = str(uuid4())
    dataset_id = str(uuid4())
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    'INSERT INTO "user" (id, username, password, is_active, is_superuser, create_at, updated_at) '
                    "VALUES (:id, :username, 'x', true, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"id": owner_id, "username": f"evals-upgrade-{owner_id}"},
            )
            has_evals = inspect(connection).has_table("dataset")
            if has_evals:
                connection.execute(
                    text(
                        "INSERT INTO dataset (id, user_id, name, revision, created_at, updated_at) "
                        "VALUES (:id, :user_id, 'retained-dataset', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    ),
                    {"id": dataset_id, "user_id": owner_id},
                )

        command.upgrade(config, "head")
        command.check(config)

        with engine.connect() as connection:
            assert connection.execute(text('SELECT id FROM "user" WHERE id = :id'), {"id": owner_id}).scalar()
            assert inspect(connection).has_table("dataset")
            assert "completed_registration_id" in {
                column["name"] for column in inspect(connection).get_columns("connection_oauth")
            }
            if has_evals:
                assert (
                    connection.execute(text("SELECT name FROM dataset WHERE id = :id"), {"id": dataset_id}).scalar()
                    == "retained-dataset"
                )
            assert MigrationContext.configure(connection).get_current_heads() == (
                ScriptDirectory.from_config(config).get_current_head(),
            )

        command.downgrade(config, starting_revision)
        with engine.connect() as connection:
            # The other history keeps whatever head it reached, so only this side is pinned.
            assert starting_revision in set(MigrationContext.configure(connection).get_current_heads())
            assert inspect(connection).has_table("dataset")
            assert "completed_registration_id" in {
                column["name"] for column in inspect(connection).get_columns("connection_oauth")
            }
            assert connection.execute(text('SELECT id FROM "user" WHERE id = :id'), {"id": owner_id}).scalar()
        command.upgrade(config, "head")
        command.check(config)
    finally:
        engine.dispose()
