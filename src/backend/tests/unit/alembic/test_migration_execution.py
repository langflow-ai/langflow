import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from langflow.services.database.models.base import LangflowBaseModel
from sqlalchemy import create_engine, inspect


def _get_alembic_cfg(db_path: str) -> Config:
    """Create an Alembic Config pointing at the project's migration scripts."""
    alembic_cfg = Config()
    workspace_root = Path(__file__).resolve().parents[5]
    script_location = workspace_root / "src/backend/base/langflow/alembic"

    if not script_location.exists():
        pytest.fail(f"Alembic script location not found at {script_location}")

    alembic_cfg.set_main_option("script_location", str(script_location))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    return alembic_cfg


EXPECTED_TABLES = {
    "user",
    "flow",
    "folder",
    "apikey",
    "variable",
    "file",
    "message",
    "transaction",
    "vertex_build",
    "job",
    "trace",
}

EXPECTED_COLUMNS = {
    "user": {"id", "username", "password"},
    "flow": {"id", "name", "user_id", "folder_id", "data"},
    "folder": {"id", "name"},
    "message": {"id", "text", "flow_id", "session_id"},
}

EXPECTED_FOREIGN_KEYS = {
    "flow": {"user.id", "folder.id"},
}


def test_migrated_schema_has_expected_tables():
    """Migrate a fresh DB to head and verify the schema is correct."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        alembic_cfg = _get_alembic_cfg(db_path)
        command.upgrade(alembic_cfg, "head")

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            insp = inspect(engine)
            actual_tables = set(insp.get_table_names())

            missing_tables = EXPECTED_TABLES - actual_tables
            assert not missing_tables, f"Missing tables after migration: {missing_tables}"

            for table, expected_cols in EXPECTED_COLUMNS.items():
                actual_cols = {col["name"] for col in insp.get_columns(table)}
                missing_cols = expected_cols - actual_cols
                assert not missing_cols, f"Table '{table}' missing columns: {missing_cols}"

            for table, expected_fk_targets in EXPECTED_FOREIGN_KEYS.items():
                fks = insp.get_foreign_keys(table)
                actual_fk_targets = {
                    f"{fk['referred_table']}.{fk['referred_columns'][0]}" for fk in fks if fk["referred_columns"]
                }
                missing_fks = expected_fk_targets - actual_fk_targets
                assert not missing_fks, f"Table '{table}' missing foreign keys to: {missing_fks}"
        finally:
            engine.dispose()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_no_phantom_migrations():
    """Verify that models and migrations are in sync.

    After migrating a fresh database to head, autogenerate should detect
    no additional changes. This catches cases where dependency upgrades
    (e.g. pydantic, sqlmodel) change how column metadata is emitted,
    which would produce unintended migration diffs.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        alembic_cfg = _get_alembic_cfg(db_path)
        command.upgrade(alembic_cfg, "head")

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                migration_context = MigrationContext.configure(connection)
                diffs = compare_metadata(migration_context, LangflowBaseModel.metadata)
        finally:
            engine.dispose()

        # Filter out diffs that are known SQLite limitations:
        # - modify_nullable: SQLite doesn't support ALTER COLUMN
        # - remove_fk/add_fk: SQLite doesn't track FK names or ondelete, so
        #   autogenerate sees phantom FK changes
        _sqlite_noise = {"modify_nullable", "remove_fk", "add_fk"}
        significant_diffs = [d for d in diffs if not (isinstance(d, tuple) and len(d) >= 2 and d[0] in _sqlite_noise)]

        if significant_diffs:
            diff_descriptions = "\n".join(str(d) for d in significant_diffs)
            pytest.fail(
                f"Autogenerate detected {len(significant_diffs)} unexpected change(s) "
                f"after migrating to head. This likely means a dependency upgrade changed "
                f"how column metadata is generated.\n\nDiffs:\n{diff_descriptions}"
            )
    finally:
        Path(db_path).unlink(missing_ok=True)
