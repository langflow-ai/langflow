"""The consent table must round-trip on every supported SQL backend."""

from alembic import command
from sqlalchemy import create_engine, inspect

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401


def test_oauth_migration_round_trip(db_url):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, "f3b6a9d2e4c1")  # pragma: allowlist secret - migration revision
    command.upgrade(config, "a7d8e9f0b1c2")  # pragma: allowlist secret - migration revision
    engine = create_engine(_engine_url(db_url))
    with engine.connect() as connection:
        columns = {col["name"] for col in inspect(connection).get_columns("connection_oauth")}
        assert {"state_digest", "encrypted_verifier", "generation"} <= columns
        assert "access_token" not in columns
    engine.dispose()
    command.downgrade(config, "f3b6a9d2e4c1")  # pragma: allowlist secret - migration revision
    engine = create_engine(_engine_url(db_url))
    with engine.connect() as connection:
        assert "connection_oauth" not in inspect(connection).get_table_names()
        assert "connection" in inspect(connection).get_table_names()
    engine.dispose()
