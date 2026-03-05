import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from langflow.services.database.service import SQLModel
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


def _get_main_branch_head() -> str | None:
    """Get the alembic head revision that origin/main is at.

    Finds migration files new on this branch (not on origin/main), then looks up
    their down_revision to determine where main's DB would be. Uses the current
    branch's alembic ScriptDirectory since it already contains all migrations.

    Returns None if git operations fail (e.g. shallow clone without origin/main).
    """
    from alembic.script import ScriptDirectory

    workspace_root = Path(__file__).resolve().parents[5]

    try:
        # Find migration files that are new on this branch vs origin/main
        result = subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                "--diff-filter=A",
                "origin/main...HEAD",
                "--",
                "src/backend/base/langflow/alembic/versions/*.py",
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=workspace_root,
        )
        new_files = [f for f in result.stdout.strip().splitlines() if f.endswith(".py")]

        if not new_files:
            # No new migrations on this branch — head is same as main
            # Use the current branch's script directory to get the head
            alembic_cfg = Config()
            script_location = workspace_root / "src/backend/base/langflow/alembic"
            alembic_cfg.set_main_option("script_location", str(script_location))
            script = ScriptDirectory.from_config(alembic_cfg)
            heads = script.get_heads()
            return heads[0] if len(heads) == 1 else None

        # Get the down_revisions of new migrations — these point to main's head(s)
        alembic_cfg = Config()
        script_location = workspace_root / "src/backend/base/langflow/alembic"
        alembic_cfg.set_main_option("script_location", str(script_location))
        script = ScriptDirectory.from_config(alembic_cfg)

        # Collect revision IDs of all new migrations
        new_rev_ids = set()
        for fpath in new_files:
            filename = Path(fpath).name
            new_rev_ids.add(filename.split("_", 1)[0])

        # Find down_revisions that point outside the new migrations (i.e. into main)
        main_revisions = set()
        for rev_id in new_rev_ids:
            rev_script = script.get_revision(rev_id)
            if rev_script and rev_script.down_revision:
                down = rev_script.down_revision
                downs = set(down) if isinstance(down, (tuple, list)) else {down}
                # Only keep down_revisions that are NOT themselves new migrations
                main_revisions.update(downs - new_rev_ids)

        # Return the single main head, or None if ambiguous
        return main_revisions.pop() if len(main_revisions) == 1 else None
    except (subprocess.CalledProcessError, KeyError, OSError):
        return None


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


def _filter_sqlite_noise(diffs: list) -> list:
    """Filter out diffs that are known SQLite limitations.

    - modify_nullable: SQLite doesn't support ALTER COLUMN
    - remove_fk/add_fk: SQLite doesn't track FK constraint names, so autogenerate
      sees phantom FK renames. However, FK pairs where ondelete/onupdate differs
      are real mismatches and are preserved.
    """
    significant_diffs = []
    fk_removes: dict[tuple, object] = {}  # (table, col_tuple) -> ForeignKeyConstraint
    fk_adds: dict[tuple, object] = {}

    for d in diffs:
        if not (isinstance(d, tuple) and len(d) >= 2):
            significant_diffs.append(d)
            continue

        op_type = d[0]
        if op_type == "modify_nullable":
            continue
        if op_type in ("remove_fk", "add_fk"):
            fk = d[1]
            key = (fk.parent.name, tuple(sorted(c.name for c in fk.columns)))
            if op_type == "remove_fk":
                fk_removes[key] = fk
            else:
                fk_adds[key] = fk
            continue

        significant_diffs.append(d)

    # Compare FK remove/add pairs: suppress only when ondelete+onupdate match
    all_fk_keys = set(fk_removes) | set(fk_adds)
    for key in all_fk_keys:
        rm = fk_removes.get(key)
        add = fk_adds.get(key)
        if rm and add and rm.ondelete == add.ondelete and rm.onupdate == add.onupdate:
            continue  # Pure name-only diff — SQLite noise
        if rm:
            significant_diffs.append(("remove_fk", rm))
        if add:
            significant_diffs.append(("add_fk", add))

    return significant_diffs


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
                diffs = compare_metadata(migration_context, SQLModel.metadata)
        finally:
            engine.dispose()

        significant_diffs = _filter_sqlite_noise(diffs)

        if significant_diffs:
            diff_descriptions = "\n".join(str(d) for d in significant_diffs)
            pytest.fail(
                f"Autogenerate detected {len(significant_diffs)} unexpected change(s) "
                f"after migrating to head. This likely means a dependency upgrade changed "
                f"how column metadata is generated.\n\nDiffs:\n{diff_descriptions}"
            )
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_upgrade_from_main_branch():
    """Verify that a DB created at main's head revision can upgrade to the current head.

    This catches the real-world scenario: a user running on main (or the latest release)
    upgrades to a branch with new migrations. The upgrade must succeed and the resulting
    schema must match the models.
    """
    main_head = _get_main_branch_head()
    if main_head is None:
        if os.environ.get("CI"):
            pytest.fail("Could not determine main branch head revision — ensure fetch-depth: 0 and origin/main exists")
        pytest.skip("Could not determine main branch head revision (shallow clone or no origin/main)")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        alembic_cfg = _get_alembic_cfg(db_path)

        # Step 1: Create DB at main's head revision (simulates existing user DB)
        command.upgrade(alembic_cfg, main_head)

        # Step 2: Upgrade to the current branch head
        command.upgrade(alembic_cfg, "head")

        # Step 3: Verify models match the migrated DB
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                migration_context = MigrationContext.configure(connection)
                diffs = compare_metadata(migration_context, SQLModel.metadata)
        finally:
            engine.dispose()

        significant_diffs = _filter_sqlite_noise(diffs)

        if significant_diffs:
            diff_descriptions = "\n".join(str(d) for d in significant_diffs)
            pytest.fail(
                f"After upgrading from main ({main_head}) to head, "
                f"autogenerate detected {len(significant_diffs)} schema mismatch(es).\n\n"
                f"Diffs:\n{diff_descriptions}"
            )
    finally:
        Path(db_path).unlink(missing_ok=True)
