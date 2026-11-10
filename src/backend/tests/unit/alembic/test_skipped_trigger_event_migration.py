"""Filtered deliveries stay terminal and retain evidence through rollback."""

from uuid import uuid4

from alembic import command
from sqlalchemy import create_engine, inspect, text

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401
from .test_trigger_migrations import _insert_event, _seed_flow_owner_and_trigger

_PREVIOUS = "f4b8c1d2e3a6"  # pragma: allowlist secret
_REVISION = "a8e4c2f6b901"  # pragma: allowlist secret


def test_skipped_event_upgrade_and_downgrade_preserve_existing_rows(db_url):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PREVIOUS)
    engine = create_engine(_engine_url(db_url))
    trigger_id, event_id = uuid4(), uuid4()
    try:
        with engine.begin() as connection:
            _seed_flow_owner_and_trigger(connection, trigger_id)
            _insert_event(connection, trigger_id, "existing")
        command.upgrade(config, _REVISION)
        with engine.begin() as connection:
            checks = {row["name"]: row["sqltext"] for row in inspect(connection).get_check_constraints("trigger_event")}
            assert "'skipped'" in checks["ck_trigger_event_state"]
            connection.execute(
                text(
                    "INSERT INTO trigger_event (id, trigger_id, dedupe_key, state, attempt, available_at, payload, "
                    "error, created_at, updated_at) VALUES (:id, :trigger, 'filtered', 'skipped', 0, "
                    "CURRENT_TIMESTAMP, '{\"event\": \"message\"}', 'sender_not_allowed', "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"id": str(event_id), "trigger": str(trigger_id)},
            )
        command.stamp(config, _PREVIOUS)
        command.upgrade(config, _REVISION)
        command.downgrade(config, _PREVIOUS)
        with engine.connect() as connection:
            retained = connection.execute(
                text("SELECT state, error, payload FROM trigger_event WHERE id = :id"), {"id": str(event_id)}
            ).one()
            assert retained.state == "completed"
            assert retained.error == "sender_not_allowed"
            assert retained.payload in ('{"event": "message"}', {"event": "message"})
            assert connection.execute(text("SELECT COUNT(*) FROM trigger_event")).scalar_one() == 2
            assert (
                connection.execute(text("SELECT state FROM trigger_event WHERE dedupe_key = 'existing'")).scalar_one()
                == "pending"
            )
            checks = {row["name"]: row["sqltext"] for row in inspect(connection).get_check_constraints("trigger_event")}
            assert "'skipped'" not in checks["ck_trigger_event_state"]
    finally:
        engine.dispose()
