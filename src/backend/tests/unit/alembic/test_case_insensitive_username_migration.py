"""Contract tests for the case-insensitive username uniqueness migration."""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION_PATH = (
    Path(__file__).parents[3] / "base/langflow/alembic/versions/1d28fd31a982_case_insensitive_username_uniqueness.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("case_insensitive_username_uniqueness", _MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _user_table(metadata: sa.MetaData) -> sa.Table:
    # Minimal shape — only the column this migration touches.
    return sa.Table(
        "user",
        metadata,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False),
    )


def test_upgrade_creates_a_case_insensitive_unique_index():
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        user = _user_table(sa.MetaData())
        user.create(connection)
        connection.execute(user.insert().values(id=str(uuid4()), username="owner1"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        # Idempotent — a second call must not try to recreate the index.
        migration.upgrade()

        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(user.insert().values(id=str(uuid4()), username="Owner1"))
    engine.dispose()


def test_upgrade_refuses_when_a_case_insensitive_collision_already_exists():
    """Never silently pick a winner between two real, pre-existing accounts."""
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        user = _user_table(sa.MetaData())
        user.create(connection)
        connection.execute(user.insert().values(id=str(uuid4()), username="owner1"))
        connection.execute(user.insert().values(id=str(uuid4()), username="Owner1"))
        migration.op = Operations(MigrationContext.configure(connection))

        with pytest.raises(RuntimeError, match="owner1"):
            migration.upgrade()

        # The refusal must raise before any DDL runs — a third case variant
        # must still insert cleanly, proving no index was partially created.
        connection.execute(user.insert().values(id=str(uuid4()), username="OWNER1"))
    engine.dispose()


def test_downgrade_drops_the_index_and_restores_case_variant_inserts():
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        user = _user_table(sa.MetaData())
        user.create(connection)
        connection.execute(user.insert().values(id=str(uuid4()), username="owner1"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.downgrade()
        # Idempotent — a second call must not error on an already-dropped index.
        migration.downgrade()

        connection.execute(user.insert().values(id=str(uuid4()), username="Owner1"))
        assert connection.execute(sa.select(sa.func.count()).select_from(user)).scalar_one() == 2
    engine.dispose()
