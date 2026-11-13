"""Rollback coverage for the default-superuser retirement column."""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION_PATH = Path(__file__).parents[3] / "base/langflow/alembic/versions/c3e1d5a7f902_add_user_retired_at.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("user_retired_at", _MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


@pytest.mark.parametrize("reupgrade", [False, True], ids=["downgrade", "roundtrip"])
def test_retired_at_rollback_preserves_case_insensitive_username_uniqueness(reupgrade):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            user = sa.Table(
                "user",
                sa.MetaData(),
                sa.Column("id", sa.String(), primary_key=True),
                sa.Column("username", sa.String(), nullable=False),
            )
            sa.Index("ix_user_username_lower", sa.func.lower(user.c.username), unique=True)
            user.create(connection)
            connection.execute(user.insert().values(id="original", username="bob"))
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
            migration.downgrade()
            # An already-downgraded database must remain safe to retry.
            migration.downgrade()
            if reupgrade:
                migration.upgrade()

            columns = {column["name"] for column in sa.inspect(connection).get_columns("user")}
            assert ("retired_at" in columns) is reupgrade
            assert connection.execute(sa.select(user)).all() == [("original", "bob")]
            with pytest.raises(sa.exc.IntegrityError):
                connection.execute(user.insert().values(id="case-variant", username="BOB"))
    finally:
        engine.dispose()
