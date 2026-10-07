"""Existing cleanup outboxes gain nullable, bounded credential storage."""

from uuid import uuid4

from alembic import command
from sqlalchemy import create_engine, inspect, text

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PREVIOUS_REVISION = "e8c2a6f4b709"  # pragma: allowlist secret - Alembic revision
_REVISION = "f9d3b7a5c201"  # pragma: allowlist secret - Alembic revision


def test_cleanup_credentials_upgrade_preserves_existing_intents_and_downgrades(db_url):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PREVIOUS_REVISION)
    engine = create_engine(_engine_url(db_url))
    task_id = str(uuid4())
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO trigger_cleanup (id, trigger_id, user_id, provider, kind, "
                    "provider_subscription_id, provider_state) VALUES (:id, :trigger, :owner, "
                    "'microsoft', 'microsoft.calendar', 'prior-watch', '{}')"
                ),
                {"id": task_id, "trigger": str(uuid4()), "owner": str(uuid4())},
            )

        command.upgrade(config, _REVISION)
        with engine.connect() as connection:
            columns = {column["name"]: column for column in inspect(connection).get_columns("trigger_cleanup")}
            assert columns["encrypted_credential"]["nullable"]
            assert columns["credential_expires_at"]["nullable"]
            retained = connection.execute(
                text(
                    "SELECT provider_subscription_id, encrypted_credential, credential_expires_at "
                    "FROM trigger_cleanup WHERE id = :id"
                ),
                {"id": task_id},
            ).one()
            assert retained == ("prior-watch", None, None)

        command.downgrade(config, _PREVIOUS_REVISION)
        with engine.connect() as connection:
            columns = {column["name"] for column in inspect(connection).get_columns("trigger_cleanup")}
            assert "encrypted_credential" not in columns
            assert "credential_expires_at" not in columns
            assert (
                connection.execute(
                    text("SELECT provider_subscription_id FROM trigger_cleanup WHERE id = :id"), {"id": task_id}
                ).scalar_one()
                == "prior-watch"
            )

        # create_all at head also creates these columns before Alembic upgrade.
        # The migration must tolerate this supported fresh-install ordering.
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE trigger_cleanup ADD COLUMN encrypted_credential TEXT"))
            connection.execute(text("ALTER TABLE trigger_cleanup ADD COLUMN credential_expires_at TIMESTAMP"))
        command.upgrade(config, _REVISION)
    finally:
        engine.dispose()
