"""Refresh token revocation storage is additive and compatible with create_all."""

from alembic import command
from sqlalchemy import create_engine, inspect, text

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PREVIOUS_REVISION = "e4f6a8b2c1d3"  # pragma: allowlist secret - Alembic revision
_REVISION = "f5a7b9c2d4e6"  # pragma: allowlist secret - Alembic revision


def test_revocation_table_upgrade_and_downgrade(db_url):  # noqa: F811
    """The new table and expiry index can be added and removed without user changes."""
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PREVIOUS_REVISION)
    engine = create_engine(_engine_url(db_url))
    try:
        command.upgrade(config, _REVISION)
        with engine.begin() as connection:
            schema = inspect(connection)
            columns = {column["name"] for column in schema.get_columns("revoked_refresh_token")}
            assert columns == {"token_digest", "expires_at"}
            assert "ix_revoked_refresh_token_expires_at" in {
                index["name"] for index in schema.get_indexes("revoked_refresh_token")
            }
            connection.execute(
                text("INSERT INTO revoked_refresh_token (token_digest, expires_at) VALUES (:digest, :expires)"),
                {"digest": "a" * 64, "expires": "2030-01-01 00:00:00"},
            )
        command.downgrade(config, _PREVIOUS_REVISION)
        with engine.connect() as connection:
            assert not inspect(connection).has_table("revoked_refresh_token")
            assert inspect(connection).has_table("user")

        # Fresh installs may create model tables before Alembic applies revisions.
        from langflow.services.database.models.auth.refresh_token import RevokedRefreshToken

        RevokedRefreshToken.__table__.create(engine)
        command.upgrade(config, _REVISION)
    finally:
        engine.dispose()
