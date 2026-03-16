import errno
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from langflow.services.database.service import SQLModel
from sqlalchemy import create_engine

_WORKSPACE_ROOT = Path(__file__).resolve().parents[5]


def _get_alembic_cfg(db_path: str) -> Config:
    """Create an Alembic Config pointing at the project's migration scripts."""
    alembic_cfg = Config()
    script_location = _WORKSPACE_ROOT / "src/backend/base/langflow/alembic"

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

    git = shutil.which("git")
    if git is None:
        return None

    # Find migration files that are new on this branch vs origin/main
    try:
        result = subprocess.run(  # noqa: S603
            [
                git,
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
            cwd=_WORKSPACE_ROOT,
        )
    except subprocess.CalledProcessError:
        return None  # git diff failed (e.g. origin/main doesn't exist)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            return None  # git binary not found at resolved path
        raise  # unexpected OS error (disk full, permissions, etc.)

    new_files = [f for f in result.stdout.strip().splitlines() if f.endswith(".py")]

    alembic_cfg = Config()
    script_location = _WORKSPACE_ROOT / "src/backend/base/langflow/alembic"
    alembic_cfg.set_main_option("script_location", str(script_location))
    script = ScriptDirectory.from_config(alembic_cfg)

    if not new_files:
        # No new migrations on this branch — head is same as main
        heads = script.get_heads()
        if len(heads) == 1:
            return heads[0]
        if len(heads) > 1:
            pytest.fail(f"Alembic has {len(heads)} head revisions — migration branches need merging: {heads}")
        return None

    # Collect revision IDs of all new migrations
    new_rev_ids = set()
    for fpath in new_files:
        filename = Path(fpath).name
        new_rev_ids.add(filename.split("_", 1)[0])

    # Find down_revisions that point outside the new migrations (i.e. into main)
    main_revisions = set()
    for rev_id in new_rev_ids:
        rev_script = script.get_revision(rev_id)
        if rev_script is None:
            msg = f"New migration file matched revision ID '{rev_id}' but Alembic has no such revision — check filename convention"
            raise ValueError(msg)
        if rev_script.down_revision is None:
            msg = f"New migration {rev_id} has down_revision=None — it must chain from an existing migration"
            raise ValueError(msg)
        down = rev_script.down_revision
        downs = set(down) if isinstance(down, (tuple, list)) else {down}
        # Only keep down_revisions that are NOT themselves new migrations
        main_revisions.update(downs - new_rev_ids)

    if len(main_revisions) > 1:
        pytest.fail(
            f"New migrations descend from {len(main_revisions)} different base revisions — "
            f"they must share a single parent on main: {main_revisions}"
        )
    if not main_revisions:
        pytest.fail(
            f"New migrations {new_rev_ids} form a disconnected chain — "
            f"none of their down_revisions point to an existing migration on main"
        )
    return main_revisions.pop()


def _filter_sqlite_noise(diffs: list) -> list:
    """Filter out diffs that are known SQLite limitations.

    - modify_nullable: SQLite doesn't support ALTER COLUMN
    - remove_fk/add_fk: SQLite doesn't track FK constraint names or actions
      (ondelete/onupdate), so autogenerate sees phantom FK diffs. Paired
      remove/add on the same (table, columns) with identical referenced targets
      are suppressed; unpaired or re-targeted FKs are preserved.
    """
    significant_diffs = []
    fk_removes: dict = {}  # (table, col_tuple) -> ForeignKeyConstraint
    fk_adds: dict = {}

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

    # Compare FK remove/add pairs: suppress when referenced targets match.
    # We intentionally skip ondelete/onupdate comparison because SQLite's
    # PRAGMA foreign_key_list does not reliably report these actions.
    all_fk_keys = set(fk_removes) | set(fk_adds)
    for key in all_fk_keys:
        rm = fk_removes.get(key)
        add = fk_adds.get(key)
        if rm and add:
            rm_targets = sorted(
                (elem.column.table.name, elem.column.name) for elem in rm.elements if elem.column is not None
            )
            add_targets = sorted(
                (elem.column.table.name, elem.column.name) for elem in add.elements if elem.column is not None
            )
            if rm_targets and rm_targets == add_targets:
                continue  # Same target — name-only or action-only diff is SQLite noise
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
    """Verify that a DB at main's head can upgrade to current head and downgrade back.

    This catches the real-world scenario: a user running on main (or the latest release)
    upgrades to a branch with new migrations. The upgrade must succeed, the resulting
    schema must match the models, and downgrade back to main must also succeed.
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

        # Step 4: Downgrade back to main's head to verify rollback works
        command.downgrade(alembic_cfg, main_head)

        # Step 5: Verify the DB is actually at main's revision after downgrade
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                ctx = MigrationContext.configure(connection)
                current_rev = ctx.get_current_revision()
                assert current_rev == main_head, (
                    f"After downgrade, expected revision {main_head} but got {current_rev}"
                )
        finally:
            engine.dispose()
    finally:
        Path(db_path).unlink(missing_ok=True)
