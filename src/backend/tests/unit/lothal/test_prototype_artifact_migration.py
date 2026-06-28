"""The U.1 schema migration: prototype linkage columns + ``lothal_prototype_artifact``.

Covers the Alembic ``upgrade()``/``downgrade()`` running against a real (SQLite)
connection: the four linkage/status columns appear (``prototype_status`` defaulting
to ``IDLE`` on existing rows), the artifact table is created, the linkage fields and
an artifact row (incl. a JSON ``manifest``) round-trip, re-runs are no-ops, an absent
table is a clean no-op, and downgrade drops the column set and the table. Driven
through Alembic's ``Operations`` context so the migration's ``op.get_bind()`` /
``migration.*`` calls resolve exactly as they do in a real upgrade.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

# Load the migration module by path (the versions dir isn't an import package).
_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "base/langflow/alembic/versions/c7d8e9f0a1b2_lothal_add_prototype_linkage_and_artifacts.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("u1_migration", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed(conn) -> None:
    # The pre-U.1 lothal_project shape (post-E.1): the columns the migration runs
    # against, but WITHOUT the four prototype columns it adds.
    conn.execute(
        sa.text(
            "CREATE TABLE lothal_project ("
            "id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, phase TEXT NOT NULL, "
            "prd_content TEXT, diagram_json TEXT, diagram_d2 TEXT, artifacts JSON, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
    )
    conn.execute(
        sa.text(
            "INSERT INTO lothal_project (id, user_id, name, phase, created_at, updated_at) "
            "VALUES ('p1', 'u1', 'p1', 'ARCHITECTURE', '2026-01-01', '2026-01-01')"
        )
    )


def _columns(conn) -> set[str]:
    return {row[1] for row in conn.execute(sa.text("PRAGMA table_info(lothal_project)")).fetchall()}


def _tables(conn) -> set[str]:
    return {row[0] for row in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}


_NEW_COLUMNS = {"od_project_id", "od_conversation_id", "prototype_status", "prototype_approved_at"}


def test_upgrade_adds_columns_and_artifact_table():
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        _seed(conn)
        assert not (_NEW_COLUMNS & _columns(conn))
        assert "lothal_prototype_artifact" not in _tables(conn)

        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()

        # 1. All four linkage/status columns now exist.
        assert _columns(conn) >= _NEW_COLUMNS
        # 2. The retained-artifact table now exists.
        assert "lothal_prototype_artifact" in _tables(conn)
        # 3. The existing row gets the IDLE default; nullable links stay NULL.
        row = conn.execute(
            sa.text(
                "SELECT prototype_status, od_project_id, od_conversation_id, prototype_approved_at "
                "FROM lothal_project WHERE id='p1'"
            )
        ).fetchone()
        assert row == ("IDLE", None, None, None)


def test_linkage_fields_and_artifact_row_round_trip():
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        _seed(conn)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()

        # Linkage fields round-trip on the project row.
        conn.execute(
            sa.text(
                "UPDATE lothal_project SET od_project_id='od-123', od_conversation_id='conv-9', "
                "prototype_status='APPROVED', prototype_approved_at='2026-06-28T00:00:00' WHERE id='p1'"
            )
        )
        row = conn.execute(
            sa.text(
                "SELECT od_project_id, od_conversation_id, prototype_status, prototype_approved_at "
                "FROM lothal_project WHERE id='p1'"
            )
        ).fetchone()
        assert row == ("od-123", "conv-9", "APPROVED", "2026-06-28T00:00:00")

        # An artifact row round-trips, with the manifest going through a typed
        # `sa.JSON()` column (native dict in, native dict out) — the same bind/
        # result conversion the ORM's `Column(JSON)` field relies on.
        artifact = sa.table(
            "lothal_prototype_artifact",
            sa.column("id", sa.Text()),
            sa.column("project_id", sa.Text()),
            sa.column("od_path", sa.Text()),
            sa.column("kind", sa.Text()),
            sa.column("title", sa.Text()),
            sa.column("manifest", sa.JSON()),
            sa.column("content", sa.Text()),
            sa.column("created_at", sa.Text()),
        )
        manifest = {"version": 1, "kind": "screen", "renderer": "html", "exports": ["index.html"]}
        conn.execute(
            sa.insert(artifact).values(
                id="a1",
                project_id="p1",
                od_path="screens/home.html",
                kind="screen",
                title="Home",
                manifest=manifest,
                content="<html>...</html>",
                created_at="2026-06-28T00:00:00",
            )
        )
        stored = conn.execute(
            sa.select(artifact.c.project_id, artifact.c.od_path, artifact.c.manifest, artifact.c.content).where(
                artifact.c.id == "a1"
            )
        ).fetchone()
        assert stored == ("p1", "screens/home.html", manifest, "<html>...</html>")


def test_upgrade_is_idempotent():
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        _seed(conn)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            migration.upgrade()  # second run must not raise or change anything
        assert _columns(conn) >= _NEW_COLUMNS
        assert "lothal_prototype_artifact" in _tables(conn)


def test_upgrade_is_noop_when_table_absent():
    """A fresh DB without the lothal table must not raise — the guard returns early."""
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn, Operations.context(MigrationContext.configure(conn)):
        migration.upgrade()  # no lothal_project table → clean no-op


def test_downgrade_drops_columns_and_table():
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        _seed(conn)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            migration.downgrade()
        assert not (_NEW_COLUMNS & _columns(conn))
        assert "lothal_prototype_artifact" not in _tables(conn)
