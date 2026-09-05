"""Portable migration coverage for the trigger entity and its event ledger.

The deduplication guarantee is the point of these tests: a second row with the
same ``(trigger_id, dedupe_key)`` must be rejected by the database, not by
application code, on both SQLite and Postgres.
"""

from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "a7d8e9f0b1c2"  # pragma: allowlist secret
_REVISION = "b7c4e1a9d3f2"  # pragma: allowlist secret

_TRIGGER_TABLES = {
    "trigger",
    "trigger_event",
    "trigger_lease",
    "trigger_listener_lease",
    "trigger_subscription",
}


def _seed_flow_owner_and_trigger(connection, trigger_id):
    """Insert the minimum owner/flow/trigger chain the ledger's FKs require."""
    user_id = uuid4()
    flow_id = uuid4()
    connection.execute(
        text(
            'INSERT INTO "user" (id, username, password, is_active, is_superuser, create_at, updated_at) '
            "VALUES (:id, :username, 'x', true, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {"id": str(user_id), "username": f"trigger-owner-{user_id.hex[:8]}"},
    )
    connection.execute(
        text("INSERT INTO flow (id, name, user_id) VALUES (:id, :name, :user_id)"),
        {"id": str(flow_id), "name": f"flow-{flow_id.hex[:8]}", "user_id": str(user_id)},
    )
    connection.execute(
        text(
            "INSERT INTO trigger (id, flow_id, user_id, name, kind, config, provider_state, state, "
            "binding_target, session_policy, concurrency_limit, max_attempts, created_at, updated_at) "
            "VALUES (:id, :flow_id, :user_id, 'digest', 'schedule', '{}', '{}', 'active', "
            "'flow', 'per_event', 1, 5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {"id": str(trigger_id), "flow_id": str(flow_id), "user_id": str(user_id)},
    )


def _insert_event(connection, trigger_id, dedupe_key):
    connection.execute(
        text(
            "INSERT INTO trigger_event (id, trigger_id, dedupe_key, state, attempt, available_at, payload, "
            "created_at, updated_at) VALUES (:id, :trigger_id, :dedupe_key, 'pending', 0, CURRENT_TIMESTAMP, "
            "'{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {"id": str(uuid4()), "trigger_id": str(trigger_id), "dedupe_key": dedupe_key},
    )


def test_trigger_migration_round_trip_sqlite_and_postgres(db_url):  # noqa: F811
    """Every trigger table is created by one revision and removed by its downgrade."""
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PRIOR_REVISION)
    command.upgrade(config, _REVISION)

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            assert set(inspector.get_table_names()) >= _TRIGGER_TABLES
            event_indexes = {index["name"] for index in inspector.get_indexes("trigger_event")}
            unique_constraints = {c["name"] for c in inspector.get_unique_constraints("trigger_event")}
            assert "uq_trigger_event_trigger_dedupe" in (event_indexes | unique_constraints)
            trigger_columns = {column["name"] for column in inspector.get_columns("trigger")}
            # TRG-4 ingress columns ship here so provider ingress needs no migration.
            assert {"public_id", "signing_secret_encrypted", "flow_version_id"} <= trigger_columns
    finally:
        engine.dispose()

    command.downgrade(config, _PRIOR_REVISION)
    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            assert not (_TRIGGER_TABLES & set(inspect(connection).get_table_names()))
    finally:
        engine.dispose()


def test_duplicate_dedupe_key_is_rejected_by_the_database(db_url):  # noqa: F811
    """The unique index — not application code — is the deduplication guarantee."""
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _REVISION)

    engine = create_engine(_engine_url(db_url))
    trigger_id = uuid4()
    try:
        with engine.begin() as connection:
            _seed_flow_owner_and_trigger(connection, trigger_id)
            _insert_event(connection, trigger_id, "tick:2026-09-05T08:00:00+00:00")

        with pytest.raises(IntegrityError), engine.begin() as connection:
            _insert_event(connection, trigger_id, "tick:2026-09-05T08:00:00+00:00")

        # A different trigger may legitimately use the same key.
        other_trigger_id = uuid4()
        with engine.begin() as connection:
            _seed_flow_owner_and_trigger(connection, other_trigger_id)
            _insert_event(connection, other_trigger_id, "tick:2026-09-05T08:00:00+00:00")

        with engine.connect() as connection:
            total = connection.execute(text("SELECT COUNT(*) FROM trigger_event")).scalar()
        assert total == 2
    finally:
        engine.dispose()
