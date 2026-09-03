"""Portable migration coverage for connection metadata and secret isolation."""

from alembic import command
from sqlalchemy import create_engine, inspect

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "c9f2e5a7b1d4"  # pragma: allowlist secret
_REVISION = "f3b6a9d2e4c1"  # pragma: allowlist secret


def test_connection_migration_round_trip_sqlite_and_postgres(db_url):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PRIOR_REVISION)
    command.upgrade(config, _REVISION)

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            assert {"connection", "connection_secret"} <= set(inspector.get_table_names())
            assert "encrypted_payload" not in {column["name"] for column in inspector.get_columns("connection")}
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
