import errno
import os
import re
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
from sqlalchemy import create_engine, text

_WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
_SCRIPT_LOCATION = _WORKSPACE_ROOT / "src/backend/base/langflow/alembic"


def _make_alembic_cfg(db_url: str) -> Config:
    """Create an Alembic Config pointing at the project's migration scripts."""
    alembic_cfg = Config()

    if not _SCRIPT_LOCATION.exists():
        pytest.fail(f"Alembic script location not found at {_SCRIPT_LOCATION}")

    alembic_cfg.set_main_option("script_location", str(_SCRIPT_LOCATION))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    return alembic_cfg


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


def _normalize_pg_url(url: str) -> str:
    """Ensure a Postgres URL uses the psycopg (v3) async-capable driver.

    Alembic's env.py uses async_engine_from_config, which requires an
    async-capable dialect. The psycopg driver supports both sync and async.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def _pg_url() -> str | None:
    """Return a PostgreSQL URL from the environment, or None."""
    url = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if url is not None:
        return _normalize_pg_url(url)
    return None


def _create_pg_test_database(base_url: str, db_name: str) -> str:
    """Create an isolated test database and return its URL."""
    engine = create_engine(base_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    # db_name is generated internally from a hash, not user input
                    f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "  # noqa: S608
                    f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid()"
                )
            )
            conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
            conn.execute(text(f"CREATE DATABASE {db_name}"))
    finally:
        engine.dispose()
    return base_url.rsplit("/", 1)[0] + f"/{db_name}"


def _drop_pg_test_database(base_url: str, db_name: str) -> None:
    """Drop the test database."""
    engine = create_engine(base_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    # db_name is generated internally from a hash, not user input
                    f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "  # noqa: S608
                    f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid()"
                )
            )
            conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
    finally:
        engine.dispose()


@pytest.fixture(params=["sqlite", "postgres"])
def db_url(request):
    """Parametrized fixture that yields a database URL for each backend."""
    if request.param == "sqlite":
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        yield f"sqlite+aiosqlite:///{db_path}"
        for suffix in ("", "-wal", "-shm", "-journal"):
            Path(db_path + suffix).unlink(missing_ok=True)
    else:
        base_url = _pg_url()
        if base_url is None:
            pytest.skip("LANGFLOW_TEST_DATABASE_URI not set")
        # Use a unique DB name per test to allow parallel execution
        import hashlib

        short_hash = hashlib.md5(request.node.name.encode()).hexdigest()[:10]  # noqa: S324
        db_name = f"lf_mig_test_{short_hash}"
        test_url = _create_pg_test_database(base_url, db_name)
        yield test_url
        _drop_pg_test_database(base_url, db_name)


def _parse_revision_values(line: str) -> list[str]:
    """Extract revision ID(s) from a line like ``revision: str = "abc123"``.

    Handles single strings, tuples of strings, and None.  Returns a list of
    zero or more revision ID strings.
    """
    if "=" not in line:
        return []
    raw = line.split("=", 1)[1]
    # Strip inline comments (e.g. "# pragma: allowlist secret")
    if "#" in raw:
        raw = raw[: raw.index("#")]
    raw = raw.strip()
    if raw == "None":
        return []
    # Extract all quoted strings from the value (handles both single values
    # and tuples like ("abc", "def"))
    return re.findall(r"""["']([a-f0-9]+)["']""", raw)


def _get_main_branch_head() -> str | None:
    """Get the alembic head revision that origin/main is at.

    Uses ``git grep`` to read the ``revision`` and ``down_revision`` variables
    directly from migration files on origin/main, then walks the chain to find
    the head revision.  This avoids relying on filename conventions (which may
    not match the actual revision IDs inside the files) and works regardless of
    whether the branch adds, modifies, or deletes migration files.

    Returns None if git operations fail (e.g. shallow clone without origin/main).
    """
    git = shutil.which("git")
    if git is None:
        return None

    def _git_grep(pattern: str) -> str | None:
        try:
            result = subprocess.run(  # noqa: S603
                [
                    git,
                    "grep",
                    "-h",
                    pattern,
                    "origin/main",
                    "--",
                    "src/backend/base/langflow/alembic/versions/",
                ],
                capture_output=True,
                text=True,
                check=True,
                cwd=_WORKSPACE_ROOT,
            )
        except subprocess.CalledProcessError:
            return None
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                return None
            raise
        return result.stdout

    # Extract all revision IDs from origin/main's migration files
    rev_output = _git_grep("^revision:")
    if not rev_output:
        return None

    main_rev_ids: set[str] = set()
    for line in rev_output.strip().splitlines():
        main_rev_ids.update(_parse_revision_values(line))

    if not main_rev_ids:
        return None

    # Extract all down_revision IDs to determine the chain
    down_output = _git_grep("^down_revision:")
    referenced: set[str] = set()
    if down_output:
        for line in down_output.strip().splitlines():
            referenced.update(_parse_revision_values(line))

    # Head = revisions not referenced as down_revision by any other revision
    heads = main_rev_ids - referenced

    if len(heads) == 1:
        return heads.pop()
    if len(heads) > 1:
        pytest.fail(f"origin/main has {len(heads)} head revisions — migration branches need merging: {heads}")
    return None


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
            try:
                key = (fk.parent.name, tuple(sorted(c.name for c in fk.columns)))
            except (AttributeError, TypeError):
                significant_diffs.append(d)
                continue
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


class _FakeColumn:
    """Minimal stand-in for sqlalchemy Column used by FK constraint diffs."""

    def __init__(self, name, table_name):
        self.name = name
        self.table = type("T", (), {"name": table_name})()


class _FakeElement:
    """Minimal stand-in for FK constraint element with a .column attribute."""

    def __init__(self, column):
        self.column = column


class _FakeFK:
    """Minimal stand-in for ForeignKeyConstraint used by autogenerate diffs."""

    def __init__(self, parent_table, col_names, ref_table, ref_col_names):
        self.parent = type("T", (), {"name": parent_table})()
        self.columns = [_FakeColumn(c, parent_table) for c in col_names]
        self.elements = [_FakeElement(_FakeColumn(rc, ref_table)) for rc in ref_col_names]


class TestFilterSqliteNoise:
    """Tests for _filter_sqlite_noise FK pair suppression logic."""

    def test_paired_fk_same_target_suppressed(self):
        """Paired remove_fk/add_fk on same columns with same target is noise."""
        fk_rm = _FakeFK("flow", ["user_id"], "user", ["id"])
        fk_add = _FakeFK("flow", ["user_id"], "user", ["id"])
        diffs = [("remove_fk", fk_rm), ("add_fk", fk_add)]
        assert _filter_sqlite_noise(diffs) == []

    def test_unpaired_remove_fk_preserved(self):
        """A remove_fk without matching add_fk is kept."""
        fk_rm = _FakeFK("flow", ["user_id"], "user", ["id"])
        diffs = [("remove_fk", fk_rm)]
        result = _filter_sqlite_noise(diffs)
        assert len(result) == 1
        assert result[0][0] == "remove_fk"

    def test_unpaired_add_fk_preserved(self):
        """An add_fk without matching remove_fk is kept."""
        fk_add = _FakeFK("flow", ["user_id"], "user", ["id"])
        diffs = [("add_fk", fk_add)]
        result = _filter_sqlite_noise(diffs)
        assert len(result) == 1
        assert result[0][0] == "add_fk"

    def test_paired_fk_different_target_preserved(self):
        """Paired remove_fk/add_fk pointing to different tables is a real change."""
        fk_rm = _FakeFK("flow", ["user_id"], "user", ["id"])
        fk_add = _FakeFK("flow", ["user_id"], "account", ["id"])
        diffs = [("remove_fk", fk_rm), ("add_fk", fk_add)]
        result = _filter_sqlite_noise(diffs)
        assert len(result) == 2

    def test_modify_nullable_always_suppressed(self):
        """modify_nullable diffs are always SQLite noise."""
        diffs = [("modify_nullable", "some_table", "some_col", {}, None, True)]
        assert _filter_sqlite_noise(diffs) == []

    def test_non_fk_diffs_preserved(self):
        """Non-FK diffs like add_column pass through unchanged."""
        diffs = [("add_column", "table", "col")]
        result = _filter_sqlite_noise(diffs)
        assert result == diffs


def _engine_url(db_url: str) -> str:
    """Convert an async DB URL to a sync one for SQLAlchemy create_engine."""
    if db_url.startswith("sqlite+aiosqlite"):
        return db_url.replace("sqlite+aiosqlite", "sqlite", 1)
    return db_url


# Postgres-only expression indexes from migrations; not mirrored in SQLModel.metadata.
_MESSAGE_SESSION_METADATA_EXPRESSION_INDEX_NAMES = frozenset(
    {
        "ix_message_session_metadata_tenant",
        "ix_message_session_metadata_user",
    }
)


def _filter_expression_index_metadata_noise(diffs: list) -> list:
    """Drop autogenerate index diffs for known migration-only expression indexes."""
    out: list = []
    for d in diffs:
        if isinstance(d, tuple) and len(d) >= 2 and d[0] in {"add_index", "remove_index"}:
            idx = d[1]
            name = getattr(idx, "name", None)
            if name in _MESSAGE_SESSION_METADATA_EXPRESSION_INDEX_NAMES:
                continue
        out.append(d)
    return out


def _filter_diffs(diffs: list, db_url: str) -> list:
    """Apply backend-appropriate diff filtering."""
    filtered_diffs = list(diffs)
    if "sqlite" in db_url:
        filtered_diffs = _filter_sqlite_noise(filtered_diffs)
    else:
        filtered_diffs = _filter_expression_index_metadata_noise(filtered_diffs)
    return filtered_diffs


class TestFilterExpressionIndexMetadataNoise:
    """Tests for filtering migration-only expression index autogenerate noise."""

    def test_known_session_metadata_indexes_suppressed(self):
        class _FakeIdx:
            name = "ix_message_session_metadata_tenant"

        class _FakeIdx2:
            name = "ix_message_session_metadata_user"

        diffs = [("remove_index", _FakeIdx()), ("remove_index", _FakeIdx2())]
        assert _filter_expression_index_metadata_noise(diffs) == []

    def test_other_index_diffs_preserved(self):
        class _FakeIdx:
            name = "ix_message_session_id"

        diffs = [("remove_index", _FakeIdx())]
        assert _filter_expression_index_metadata_noise(diffs) == diffs


def test_no_phantom_migrations(db_url):
    """Verify that models and migrations are in sync.

    After migrating a fresh database to head, autogenerate should detect
    no additional changes. This catches cases where dependency upgrades
    (e.g. pydantic, sqlmodel) change how column metadata is emitted,
    which would produce unintended migration diffs.
    """
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            migration_context = MigrationContext.configure(connection)
            diffs = compare_metadata(migration_context, SQLModel.metadata)
    finally:
        engine.dispose()

    significant_diffs = _filter_diffs(diffs, db_url)

    if significant_diffs:
        diff_descriptions = "\n".join(str(d) for d in significant_diffs)
        pytest.fail(
            f"Autogenerate detected {len(significant_diffs)} unexpected change(s) "
            f"after migrating to head. This likely means a dependency upgrade changed "
            f"how column metadata is generated.\n\nDiffs:\n{diff_descriptions}"
        )


def test_upgrade_from_main_branch(db_url):
    """Verify that a DB at main's head can upgrade to current head and downgrade back.

    This catches the real-world scenario: a user running on main (or the latest release)
    upgrades to a branch with new migrations. The upgrade must succeed, the resulting
    schema must match the models, and downgrade back to main must also succeed.
    """
    from alembic.script import ScriptDirectory

    main_head = _get_main_branch_head()
    if main_head is None:
        if os.environ.get("MIGRATION_VALIDATION_CI"):
            pytest.fail("Could not determine main branch head revision — ensure fetch-depth: 0 and origin/main exists")
        pytest.skip("Could not determine main branch head revision (shallow clone or no origin/main)")

    # Check if main and branch share the same alembic head (no new migrations).
    # In that case this test is a no-op — alembic won't re-run already-applied
    # migrations, so upgrade(main_head) -> upgrade(head) does nothing.
    # Modified migrations are exercised by test_no_phantom_migrations instead.
    branch_cfg = Config()
    branch_cfg.set_main_option("script_location", str(_SCRIPT_LOCATION))
    branch_script = ScriptDirectory.from_config(branch_cfg)
    branch_heads = branch_script.get_heads()
    if len(branch_heads) == 1 and branch_heads[0] == main_head:
        pytest.skip(
            "No new migrations on this branch — main and branch share the same "
            "alembic head. Modified migrations are tested by test_no_phantom_migrations."
        )

    alembic_cfg = _make_alembic_cfg(db_url)

    # Step 1: Create DB at main's head revision (simulates existing user DB)
    command.upgrade(alembic_cfg, main_head)

    # Step 2: Upgrade to the current branch head
    command.upgrade(alembic_cfg, "head")

    # Step 3: Verify models match the migrated DB
    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            migration_context = MigrationContext.configure(connection)
            diffs = compare_metadata(migration_context, SQLModel.metadata)
    finally:
        engine.dispose()

    significant_diffs = _filter_diffs(diffs, db_url)

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
    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            ctx = MigrationContext.configure(connection)
            current_rev = ctx.get_current_revision()
            assert current_rev == main_head, f"After downgrade, expected revision {main_head} but got {current_rev}"
    finally:
        engine.dispose()
