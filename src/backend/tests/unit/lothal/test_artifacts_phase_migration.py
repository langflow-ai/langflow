"""The E.1 schema migration: add ``artifacts`` + remap diagram phases to ARCHITECTURE.

Covers the Alembic ``upgrade()``/``downgrade()`` running against a real (SQLite)
connection: the new column appears, existing rows on the two old diagram phases
land on ``ARCHITECTURE``, every other phase is left alone, an ``artifacts`` map
round-trips through the JSON column, and re-runs are no-ops. Driven through
Alembic's ``Operations`` context so the migration's ``op.get_bind()`` /
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
    / "base/langflow/alembic/versions/e1f0a2b3c4d5_lothal_add_artifacts_and_merge_architecture_phase.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("e1_migration", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed(conn) -> None:
    # The pre-E.1 lothal_project shape: every NOT NULL column the migration runs
    # against in production, but WITHOUT the artifacts column the migration adds.
    conn.execute(
        sa.text(
            "CREATE TABLE lothal_project ("
            "id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, phase TEXT NOT NULL, "
            "prd_content TEXT, diagram_json TEXT, diagram_d2 TEXT, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
    )

    def _insert(pid: str, phase: str) -> None:
        conn.execute(
            sa.text(
                "INSERT INTO lothal_project "
                "(id, user_id, name, phase, created_at, updated_at) "
                "VALUES (:id, 'u1', :name, :phase, '2026-01-01', '2026-01-01')"
            ),
            {"id": pid, "name": pid, "phase": phase},
        )

    _insert("p_gen", "DIAGRAM_GENERATION")  # old gen phase  → ARCHITECTURE
    _insert("p_ref", "DIAGRAM_REFINEMENT")  # old refine phase → ARCHITECTURE
    _insert("p_clar", "CLARIFICATION")  # untouched
    _insert("p_code", "CODE_GENERATION")  # untouched
    _insert("p_done", "DONE")  # untouched


def _phase_by_id(conn) -> dict[str, str]:
    return dict(conn.execute(sa.text("SELECT id, phase FROM lothal_project")).fetchall())


def _columns(conn) -> set[str]:
    return {row[1] for row in conn.execute(sa.text("PRAGMA table_info(lothal_project)")).fetchall()}


def test_upgrade_adds_column_and_remaps_diagram_phases():
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        _seed(conn)
        assert "artifacts" not in _columns(conn)

        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()

        # 1. The generic artifact column now exists.
        assert "artifacts" in _columns(conn)

        # 2. Both old diagram phases collapse onto ARCHITECTURE; nothing else moves.
        phases = _phase_by_id(conn)
        assert phases["p_gen"] == "ARCHITECTURE"
        assert phases["p_ref"] == "ARCHITECTURE"
        assert phases["p_clar"] == "CLARIFICATION"
        assert phases["p_code"] == "CODE_GENERATION"
        assert phases["p_done"] == "DONE"


def test_artifacts_map_round_trips():
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        _seed(conn)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()

        # Go through a typed `sa.JSON()` column so the round-trip exercises the
        # same bind/result conversion the ORM's `Column(JSON)` field relies on —
        # a native dict in, a native dict out — not just raw string storage.
        artifacts = sa.table(
            "lothal_project",
            sa.column("id", sa.Text()),
            sa.column("artifacts", sa.JSON()),
        )
        artifact_map = {
            "adr.md": "# Architecture Decision Record\n...",
            "diagrams/context.d2": "direction: right\nuser: User {shape: person}",
            "diagrams/sequence.d2": "shape: sequence_diagram\nuser: User",
        }
        conn.execute(sa.update(artifacts).where(artifacts.c.id == "p_gen").values(artifacts=artifact_map))
        stored = conn.execute(sa.select(artifacts.c.artifacts).where(artifacts.c.id == "p_gen")).scalar()
        # The JSON column deserialises back to the original dict, not a string.
        assert stored == artifact_map
        # Rows with no artifacts stay NULL (no backfill).
        assert conn.execute(sa.select(artifacts.c.artifacts).where(artifacts.c.id == "p_ref")).scalar() is None


def test_upgrade_is_idempotent():
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        _seed(conn)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            first = _phase_by_id(conn)
            migration.upgrade()  # second run must not raise or change anything
            second = _phase_by_id(conn)
        assert first == second
        assert "artifacts" in _columns(conn)


def test_upgrade_is_noop_when_table_absent():
    """A fresh DB without the lothal table must not raise — the guard returns early."""
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn, Operations.context(MigrationContext.configure(conn)):
        migration.upgrade()  # no lothal_project table → clean no-op


def test_downgrade_drops_column_and_leaves_phase_data():
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        _seed(conn)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            migration.downgrade()
        # Column is gone again...
        assert "artifacts" not in _columns(conn)
        # ...but the remapped phase data stays on ARCHITECTURE (unrecoverable split).
        phases = _phase_by_id(conn)
        assert phases["p_gen"] == "ARCHITECTURE"
        assert phases["p_ref"] == "ARCHITECTURE"
