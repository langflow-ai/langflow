"""Portable migration coverage for connection metadata and secret isolation."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from alembic import command
from sqlalchemy import JSON, Boolean, Column, DateTime, MetaData, String, Table, Uuid, create_engine, insert, inspect
from sqlalchemy.exc import IntegrityError

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "e8f0a2c4d6b9"  # pragma: allowlist secret
_REVISION = "f3b6a9d2e4c1"  # pragma: allowlist secret

# Only the columns these tests write, typed as the migrations create them.
_METADATA = MetaData()
_USERS = Table(
    "user",
    _METADATA,
    Column("id", Uuid(), primary_key=True),
    Column("username", String()),
    Column("password", String()),
    Column("is_active", Boolean()),
    Column("is_superuser", Boolean()),
    Column("create_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)
_CONNECTIONS = Table(
    "connection",
    _METADATA,
    Column("id", Uuid(), primary_key=True),
    Column("owner_id", Uuid()),
    Column("provider_key", String()),
    Column("name", String()),
    Column("display_name", String()),
    Column("ownership_mode", String()),
    Column("status", String()),
    Column("health", String()),
    Column("granted_scopes", JSON()),
    Column("executing_identity", JSON()),
)


def _user_row(user_id: UUID) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": user_id,
        "username": f"user-{user_id.hex}",
        "password": "unused-hash",  # pragma: allowlist secret
        "is_active": True,
        "is_superuser": False,
        "create_at": now,
        "updated_at": now,
    }


def _connection_row(owner_id: UUID | None) -> dict:
    return {
        "id": uuid4(),
        "owner_id": owner_id,
        "provider_key": "google_workspace",
        "name": "work",
        "display_name": "Work",
        "ownership_mode": "user" if owner_id is not None else "instance",
        "status": "pending",
        "health": "unknown",
        "granted_scopes": [],
        "executing_identity": {"identity": "user_delegated"},
    }


def test_connection_migration_round_trip_sqlite_and_postgres(db_url):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PRIOR_REVISION)
    command.upgrade(config, _REVISION)

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            assert {"connection", "connection_secret"} <= set(inspector.get_table_names())
            connection_columns = {column["name"]: column for column in inspector.get_columns("connection")}
            assert "encrypted_payload" not in connection_columns
            assert connection_columns["status_reason"]["nullable"] is True
            assert "encrypted_payload" in {column["name"] for column in inspector.get_columns("connection_secret")}
    finally:
        engine.dispose()

    command.downgrade(config, _PRIOR_REVISION)
    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            assert "connection" not in tables
            assert "connection_secret" not in tables
    finally:
        engine.dispose()


def test_connection_handles_are_unique_per_owner_and_for_the_instance(db_url):  # noqa: F811
    command.upgrade(_make_alembic_cfg(db_url), _REVISION)
    owner_a, owner_b = uuid4(), uuid4()

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            connection.execute(insert(_USERS), [_user_row(owner_a), _user_row(owner_b)])
            # One handle may exist once per user owner and once for the instance.
            connection.execute(
                insert(_CONNECTIONS),
                [_connection_row(owner_a), _connection_row(owner_b), _connection_row(None)],
            )

        for duplicate_owner in (owner_a, None):
            with pytest.raises(IntegrityError), engine.begin() as connection:
                connection.execute(insert(_CONNECTIONS).values(**_connection_row(duplicate_owner)))
    finally:
        engine.dispose()
