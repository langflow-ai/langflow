"""Tests for the legacy message-ownership backfill."""

import importlib
import types
from uuid import uuid4

import sqlalchemy as sa

_MIGRATION = importlib.import_module("langflow.alembic.versions.d49cbced8696_backfill_message_ownership")


def _run_upgrade(engine) -> None:
    with engine.begin() as conn:
        original_op = _MIGRATION.op
        try:
            _MIGRATION.op = types.SimpleNamespace(get_bind=lambda: conn)
            _MIGRATION.upgrade()
        finally:
            _MIGRATION.op = original_op


def test_upgrade_attributes_only_unowned_messages_to_flow_owner():
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

    owner = uuid4()
    existing_owner = uuid4()
    flow_id = uuid4()
    orphan_flow_id = uuid4()
    legacy_id = uuid4()
    scoped_id = uuid4()
    orphan_id = uuid4()
    with engine.begin() as conn:
        conn.execute(flow.insert(), [{"id": flow_id, "user_id": owner}])
        conn.execute(
            message.insert(),
            [
                {"id": legacy_id, "flow_id": flow_id, "user_id": None},
                {"id": scoped_id, "flow_id": flow_id, "user_id": existing_owner},
                {"id": orphan_id, "flow_id": orphan_flow_id, "user_id": None},
            ],
        )

    _run_upgrade(engine)
    _run_upgrade(engine)

    with engine.connect() as conn:
        owners = dict(conn.execute(sa.select(message.c.id, message.c.user_id)).all())
    assert owners == {legacy_id: owner, scoped_id: existing_owner, orphan_id: None}
