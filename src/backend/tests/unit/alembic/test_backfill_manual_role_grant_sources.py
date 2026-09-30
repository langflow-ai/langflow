"""Tests for the manual role-assignment grant-source backfill."""

from __future__ import annotations

import importlib
import types
from datetime import datetime, timedelta, timezone
from uuid import UUID

import sqlalchemy as sa

_MIGRATION = importlib.import_module("langflow.alembic.versions.cp02a2b3c4d5_backfill_manual_role_grant_sources")


def _make_tables():
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    assignment = sa.Table(
        "authz_role_assignment",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
    )
    grant = sa.Table(
        "authz_role_assignment_grant",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.String(), nullable=False),
        sa.Column("provider_id", sa.String(), nullable=True),
        sa.Column("external_group", sa.String(), nullable=True),
        sa.Column("administrative_actor", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(engine)
    return engine, assignment, grant


def _run_upgrade(engine) -> None:
    with engine.begin() as conn:
        original_op = _MIGRATION.op
        try:
            _MIGRATION.op = types.SimpleNamespace(get_bind=lambda: conn)
            _MIGRATION.upgrade()
        finally:
            _MIGRATION.op = original_op


def test_upgrade_backfills_deterministic_batches_without_replacing_existing_sources(monkeypatch):
    engine, assignment, grant = _make_tables()
    monkeypatch.setattr(_MIGRATION, "_BATCH_SIZE", 2)
    assignment_ids = [UUID(int=value) for value in range(1, 7)]
    actors = [UUID(int=100 + value) for value in range(1, 7)]
    assigned_at = [datetime(2026, 7, 30, 12, tzinfo=timezone.utc) + timedelta(minutes=value) for value in range(1, 7)]

    with engine.begin() as conn:
        conn.execute(
            assignment.insert(),
            [
                {
                    "id": assignment_id,
                    "assigned_by": actor,
                    "assigned_at": timestamp,
                }
                for assignment_id, actor, timestamp in zip(assignment_ids, actors, assigned_at, strict=True)
            ],
        )
        conn.execute(
            grant.insert(),
            {
                "id": UUID(int=1000),
                "assignment_id": assignment_ids[2],
                "source_kind": "idp",
                "provider_id": "example-idp",
                "external_group": "engineering",
                "administrative_actor": None,
                "created_at": assigned_at[2],
                "updated_at": assigned_at[2],
            },
        )

    batch_sizes: list[int] = []

    def record_grant_insert(_conn, _cursor, statement, parameters, _context, executemany):
        if statement.lstrip().startswith("INSERT INTO authz_role_assignment_grant"):
            batch_sizes.append(len(parameters) if executemany else 1)

    sa.event.listen(engine, "before_cursor_execute", record_grant_insert)

    _run_upgrade(engine)
    _run_upgrade(engine)

    with engine.connect() as conn:
        rows = conn.execute(sa.select(grant).order_by(grant.c.assignment_id)).mappings().all()

    assert batch_sizes == [2, 2, 1]
    assert len(rows) == len(assignment_ids)
    assert rows[2]["source_kind"] == "idp"
    assert rows[2]["provider_id"] == "example-idp"
    assert rows[2]["external_group"] == "engineering"

    manual_rows = [row for row in rows if row["source_kind"] == "manual"]
    expected = {
        assignment_id: (actor, timestamp.replace(tzinfo=None))
        for assignment_id, actor, timestamp in zip(assignment_ids, actors, assigned_at, strict=True)
        if assignment_id != assignment_ids[2]
    }
    assert {row["assignment_id"] for row in manual_rows} == expected.keys()
    for row in manual_rows:
        actor, timestamp = expected[row["assignment_id"]]
        assert row["provider_id"] is None
        assert row["external_group"] is None
        assert row["administrative_actor"] == actor
        assert row["created_at"] == timestamp
        assert row["updated_at"] == timestamp
