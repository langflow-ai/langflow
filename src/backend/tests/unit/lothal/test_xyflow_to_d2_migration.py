"""The D.13 data migration: backfill `diagram_d2` from legacy `diagram_json`.

`test_xyflow_to_d2.py` covers the pure converter; this covers the Alembic
migration that *applies* it — that `upgrade()` runs against a real (SQLite)
connection, converts only the rows that need it, leaves everything else alone,
and is safely re-runnable. Driven through Alembic's `Operations` context so the
migration's `op.get_bind()` / `migration.*` calls resolve exactly as they do in a
real upgrade.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

# Load the migration module by path (the versions dir isn't an import package).
_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "base/langflow/alembic/versions/a8f3c2e91d05_lothal_backfill_diagram_d2.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("d13_migration", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_LEGACY_GRAPH = json.dumps(
    {
        "nodes": [
            {"id": "user", "type": "actorNode", "data": {"label": "User"}},
            {"id": "api", "type": "systemNode", "data": {"label": "API"}},
        ],
        "edges": [
            {"id": "e1", "source": "user", "target": "api", "data": {"order": 1, "label": "submit"}},
            {"id": "e2", "source": "api", "target": "user", "animated": True, "data": {"order": 2, "label": "ok"}},
        ],
    }
)


def _seed(conn) -> None:
    # Mirror the real lothal_project shape — the NOT NULL columns the migration
    # runs against in production (user_id/name/phase/created_at/updated_at), not
    # just the three the migration reflects — so the backfill is exercised against
    # the actual table, and its UPDATE/SELECT can't silently depend on a stripped one.
    conn.execute(
        sa.text(
            "CREATE TABLE lothal_project ("
            "id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, phase TEXT NOT NULL, "
            "prd_content TEXT, diagram_json TEXT, diagram_d2 TEXT, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
    )

    def _insert(pid: str, diagram_json, diagram_d2) -> None:
        conn.execute(
            sa.text(
                "INSERT INTO lothal_project "
                "(id, user_id, name, phase, diagram_json, diagram_d2, created_at, updated_at) "
                "VALUES (:id, 'u1', :name, 'DIAGRAM_REFINEMENT', :j, :d2, '2026-01-01', '2026-01-01')"
            ),
            {"id": pid, "name": pid, "j": diagram_json, "d2": diagram_d2},
        )

    _insert("p1", _LEGACY_GRAPH, None)  # legacy graph, no D2 → must be converted
    _insert("p2", None, None)  # nothing to convert → stays NULL
    _insert("p3", _LEGACY_GRAPH, "EXISTING D2")  # already has D2 → never overwritten
    _insert("p4", "{not valid json", None)  # corrupt diagram_json → skipped, stays NULL
    _insert("p5", '{"nodes": [], "edges": []}', None)  # no-node graph → converter raises → skipped


def _d2_by_id(conn) -> dict[str, str | None]:
    return dict(conn.execute(sa.text("SELECT id, diagram_d2 FROM lothal_project")).fetchall())


def test_upgrade_backfills_only_legacy_rows():
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        _seed(conn)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()

        rows = _d2_by_id(conn)
        # p1's xyflow graph became a compilable D2 sequence diagram.
        assert rows["p1"] is not None
        assert rows["p1"].startswith("shape: sequence_diagram")
        assert "user -> api: submit" in rows["p1"]
        assert "api --> user: ok" in rows["p1"]  # animated edge → dashed arrow
        # p2 had nothing to convert; p3 already had D2 — neither is touched.
        assert rows["p2"] is None
        assert rows["p3"] == "EXISTING D2"
        # p4 (corrupt JSON) and p5 (no-node graph) are skipped, not crashed — the
        # migration's headline safety guarantee. They stay NULL (regenerate later),
        # and a bad row must never abort the whole migration (p1 still converted).
        assert rows["p4"] is None
        assert rows["p5"] is None


def test_compiles_treats_timeout_as_failure(monkeypatch):
    """A compile-check timeout returns False (skip the row), not None (store unvalidated)."""
    import subprocess

    migration = _load_migration()
    monkeypatch.setattr(migration.shutil, "which", lambda _name: "/usr/local/bin/d2")

    def _raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="d2", timeout=30)

    monkeypatch.setattr(migration.subprocess, "run", _raise_timeout)
    assert migration._compiles("shape: sequence_diagram\na: A") is False


def test_upgrade_skips_rows_that_fail_compile_check(monkeypatch):
    """When the converted D2 doesn't compile, the row is skipped (diagram_d2 stays NULL)."""
    migration = _load_migration()
    # Force every compile-check to "definitely failed" so the converted (otherwise
    # valid) D2 is rejected — proves the gate, not the converter, drives the skip.
    monkeypatch.setattr(migration, "_compiles", lambda _d2: False)

    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        _seed(conn)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        rows = _d2_by_id(conn)
        assert rows["p1"] is None  # convertible, but compile-check failed → not stored
        assert rows["p3"] == "EXISTING D2"  # still never touched


def test_upgrade_is_idempotent():
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        _seed(conn)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            first = _d2_by_id(conn)["p1"]
            migration.upgrade()  # a second run must not change anything
            second = _d2_by_id(conn)["p1"]
        assert first == second


def test_upgrade_is_noop_when_table_absent():
    """A fresh DB without the lothal table must not raise — the guard returns early."""
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn, Operations.context(MigrationContext.configure(conn)):
        migration.upgrade()  # no lothal_project table exists → clean no-op


def test_downgrade_is_a_noop():
    """Downgrade intentionally leaves the backfilled data in place (see the migration docstring)."""
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        _seed(conn)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            before = _d2_by_id(conn)
            migration.downgrade()
            after = _d2_by_id(conn)
        assert before == after
