"""Tests for the legacy message ownership backfill."""

from __future__ import annotations

import importlib
import types
from uuid import UUID, uuid4

import sqlalchemy as sa

_MIGRATION = importlib.import_module("langflow.alembic.versions.47aca8c17d23_backfill_message_user_id")


def _make_tables():
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    flow = sa.Table(
        "flow",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
    )
    message = sa.Table(
        "message",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("flow_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
    )
    metadata.create_all(engine)
    return engine, flow, message


def _run_upgrade(engine) -> None:
    with engine.begin() as conn:
        original_op = _MIGRATION.op
        try:
            _MIGRATION.op = types.SimpleNamespace(get_bind=lambda: conn)
            _MIGRATION.upgrade()
        finally:
            _MIGRATION.op = original_op


def _message_owners(engine, message) -> dict[UUID, UUID | None]:
    with engine.connect() as conn:
        rows = conn.execute(sa.select(message.c.id, message.c.user_id)).all()
    return {row.id: row.user_id for row in rows}


def test_upgrade_attributes_legacy_messages_to_flow_owner_without_overwriting_scoped_rows():
    engine, flow, message = _make_tables()
    owner_a = uuid4()
    owner_b = uuid4()
    preexisting_owner = uuid4()
    flow_a = uuid4()
    flow_b = uuid4()
    ownerless_flow = uuid4()
    orphan_flow = uuid4()
    legacy_a = uuid4()
    legacy_b = uuid4()
    already_scoped = uuid4()
    ownerless = uuid4()
    orphan = uuid4()
    no_flow = uuid4()

    with engine.begin() as conn:
        conn.execute(
            flow.insert(),
            [
                {"id": flow_a, "user_id": owner_a},
                {"id": flow_b, "user_id": owner_b},
                {"id": ownerless_flow, "user_id": None},
            ],
        )
        conn.execute(
            message.insert(),
            [
                {"id": legacy_a, "flow_id": flow_a, "user_id": None},
                {"id": legacy_b, "flow_id": flow_b, "user_id": None},
                {"id": already_scoped, "flow_id": flow_a, "user_id": preexisting_owner},
                {"id": ownerless, "flow_id": ownerless_flow, "user_id": None},
                {"id": orphan, "flow_id": orphan_flow, "user_id": None},
                {"id": no_flow, "flow_id": None, "user_id": None},
            ],
        )

    _run_upgrade(engine)

    assert _message_owners(engine, message) == {
        legacy_a: owner_a,
        legacy_b: owner_b,
        already_scoped: preexisting_owner,
        ownerless: None,
        orphan: None,
        no_flow: None,
    }

    # The migration is safe to retry and does not overwrite runtime-scoped rows.
    after_first_upgrade = _message_owners(engine, message)
    _run_upgrade(engine)
    assert _message_owners(engine, message) == after_first_upgrade

    # The upgraded history is visible only to the owner inferred from its flow.
    with engine.connect() as conn:
        visible_to_a = set(conn.execute(sa.select(message.c.id).where(message.c.user_id == owner_a)).scalars().all())
        visible_to_b = set(conn.execute(sa.select(message.c.id).where(message.c.user_id == owner_b)).scalars().all())
        visible_to_preexisting_runner = set(
            conn.execute(sa.select(message.c.id).where(message.c.user_id == preexisting_owner)).scalars().all()
        )
    assert visible_to_a == {legacy_a}
    assert visible_to_b == {legacy_b}
    assert visible_to_preexisting_runner == {already_scoped}
