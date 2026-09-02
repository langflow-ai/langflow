"""Tests for the flow-version payload compression migration."""

from __future__ import annotations

import gzip
import importlib
import json

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION = importlib.import_module("langflow.alembic.versions.d3b7c1e05f84_compress_flow_version_data")

GRAPH = {
    "nodes": [{"id": f"node-{index}", "data": {"code": "from lfx import Component\n" * 8}} for index in range(6)],
    "edges": [],
    "name": "Análise de Sentimento — ação",
}
POPULATED_ROWS = 5


def _engine_before_the_migration():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "flow_version",
        metadata,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
    )
    metadata.create_all(engine)
    with engine.begin() as conn:
        for index in range(POPULATED_ROWS):
            conn.execute(
                sa.text("INSERT INTO flow_version (id, data, version_number) VALUES (:id, :data, :n)"),
                {"id": f"row-{index}", "data": json.dumps(GRAPH), "n": index + 1},
            )
        conn.execute(
            sa.text("INSERT INTO flow_version (id, data, version_number) VALUES (:id, NULL, :n)"),
            {"id": "row-null", "n": POPULATED_ROWS + 1},
        )
    return engine


def _run(engine, direction: str) -> None:
    with engine.begin() as conn:
        original = _MIGRATION.op
        try:
            _MIGRATION.op = Operations(MigrationContext.configure(conn))
            getattr(_MIGRATION, direction)()
        finally:
            _MIGRATION.op = original


def _columns(engine) -> set[str]:
    return {column["name"] for column in sa.inspect(engine).get_columns("flow_version")}


def test_upgrade_compresses_every_populated_row_and_keeps_null(monkeypatch):
    monkeypatch.setattr(_MIGRATION, "BATCH_SIZE", 2)
    engine = _engine_before_the_migration()

    _run(engine, "upgrade")

    assert _columns(engine) == {"id", "data_gz", "version_number"}
    with engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT id, data_gz FROM flow_version ORDER BY version_number")).fetchall()
    stored = {row.id: row.data_gz for row in rows}
    assert stored["row-null"] is None
    for index in range(POPULATED_ROWS):
        payload = stored[f"row-{index}"]
        assert payload[:2] == b"\x1f\x8b"
        assert json.loads(gzip.decompress(payload)) == GRAPH


def test_downgrade_restores_the_original_json(monkeypatch):
    monkeypatch.setattr(_MIGRATION, "BATCH_SIZE", 2)
    engine = _engine_before_the_migration()

    _run(engine, "upgrade")
    _run(engine, "downgrade")

    assert _columns(engine) == {"id", "data", "version_number"}
    with engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT id, data FROM flow_version ORDER BY version_number")).fetchall()
    stored = {row.id: row.data for row in rows}
    assert stored["row-null"] is None
    for index in range(POPULATED_ROWS):
        assert json.loads(stored[f"row-{index}"]) == GRAPH


def test_upgrade_refuses_to_drop_the_column_when_a_row_was_not_migrated(monkeypatch):
    engine = _engine_before_the_migration()
    monkeypatch.setattr(_MIGRATION, "_rows", lambda *_: iter(()))

    with pytest.raises(RuntimeError, match="still hold data in data"):
        _run(engine, "upgrade")

    assert "data" in _columns(engine)


def test_downgrade_refuses_to_drop_the_column_when_a_row_was_not_restored(monkeypatch):
    engine = _engine_before_the_migration()
    _run(engine, "upgrade")
    monkeypatch.setattr(_MIGRATION, "_rows", lambda *_: iter(()))

    with pytest.raises(RuntimeError, match="still hold data in data_gz"):
        _run(engine, "downgrade")

    assert "data_gz" in _columns(engine)


def test_upgrade_is_a_noop_without_the_table():
    engine = sa.create_engine("sqlite://")

    _run(engine, "upgrade")

    assert not sa.inspect(engine).has_table("flow_version")
