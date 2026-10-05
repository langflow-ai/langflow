"""Recovery changes upgrade already-fenced schemas without losing deletion intent."""

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

pytestmark = pytest.mark.no_blockbuster


def test_storage_recovery_migration_retains_ledgers_and_guards_downgrade(tmp_path, monkeypatch):
    migration = importlib.import_module("langflow.alembic.versions.d42f18a9b760_storage_retirement_and_pending_purges")
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'recovery.sqlite3'}")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql("CREATE TABLE knowledge_base (id VARCHAR PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE memory_base_session (id VARCHAR PRIMARY KEY)")
        connection.exec_driver_sql(
            "CREATE TABLE knowledge_base_storage_migration (id VARCHAR PRIMARY KEY, kb_id VARCHAR NOT NULL "
            "REFERENCES knowledge_base(id) ON DELETE CASCADE)"
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        assert not sa.inspect(connection).get_foreign_keys("knowledge_base_storage_migration")
        connection.exec_driver_sql("INSERT INTO knowledge_base VALUES ('retired')")
        connection.exec_driver_sql("INSERT INTO knowledge_base_storage_migration VALUES ('ledger', 'retired')")
        connection.exec_driver_sql("DELETE FROM knowledge_base WHERE id = 'retired'")
        assert connection.exec_driver_sql("SELECT id FROM knowledge_base_storage_migration").scalar_one() == "ledger"
        with pytest.raises(RuntimeError, match="Retained storage ledgers"):
            migration.downgrade()
        connection.exec_driver_sql("DELETE FROM knowledge_base_storage_migration")
        connection.exec_driver_sql("INSERT INTO memory_base_session VALUES ('session', true)")
        with pytest.raises(RuntimeError, match="pending Memory purges"):
            migration.downgrade()
        connection.exec_driver_sql("UPDATE memory_base_session SET purge_pending = false")
        migration.downgrade()
        assert sa.inspect(connection).get_foreign_keys("knowledge_base_storage_migration")
        assert "purge_pending" not in {
            column["name"] for column in sa.inspect(connection).get_columns("memory_base_session")
        }
        migration.upgrade()
        assert connection.exec_driver_sql("SELECT purge_pending FROM memory_base_session").scalar_one() == 0
    engine.dispose()
