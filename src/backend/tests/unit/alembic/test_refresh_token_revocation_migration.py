"""Refresh token revocation storage is additive and compatible with create_all."""

from datetime import datetime, timezone
from uuid import uuid4

from alembic import command
from langflow.services.database.models.auth.refresh_token import RefreshTokenSession
from langflow.services.database.models.user.model import User
from sqlalchemy import create_engine, inspect, select

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
        with engine.connect() as connection:
            if connection.dialect.name == "sqlite":
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()
            schema = inspect(connection)
            columns = {column["name"] for column in schema.get_columns("refresh_token_session")}
            assert columns == {"session_digest", "user_id", "expires_at", "revoked"}
            assert {"ix_refresh_token_session_expires_at", "ix_refresh_token_session_user_id"} <= {
                index["name"] for index in schema.get_indexes("refresh_token_session")
            }
            foreign_key = schema.get_foreign_keys("refresh_token_session")[0]
            assert foreign_key["constrained_columns"] == ["user_id"]
            assert foreign_key["referred_table"] == "user"
            assert foreign_key["options"]["ondelete"] == "CASCADE"
            owner_id, other_id = uuid4(), uuid4()
            connection.execute(
                User.__table__.insert(),
                [{"id": user_id, "username": str(user_id), "password": "unused"} for user_id in (owner_id, other_id)],
            )
            connection.execute(
                RefreshTokenSession.__table__.insert(),
                [
                    {
                        "session_digest": digest * 64,
                        "user_id": user_id,
                        "expires_at": datetime(2030, 1, 1, tzinfo=timezone.utc),
                    }
                    for digest, user_id in (("a", owner_id), ("b", other_id))
                ],
            )
            connection.execute(User.__table__.delete().where(User.id == owner_id))
            assert connection.execute(select(RefreshTokenSession.user_id)).scalars().all() == [other_id]
            connection.commit()
        command.downgrade(config, _PREVIOUS_REVISION)
        with engine.connect() as connection:
            assert not inspect(connection).has_table("refresh_token_session")
            assert inspect(connection).has_table("user")

        # Fresh installs may create model tables before Alembic applies revisions.
        RefreshTokenSession.__table__.create(engine)
        command.upgrade(config, _REVISION)
    finally:
        engine.dispose()
