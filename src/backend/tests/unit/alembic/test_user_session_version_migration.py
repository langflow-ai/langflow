"""A nullable session version preserves users and sessions during an upgrade."""

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PREVIOUS_REVISION = "f5a7b9c2d4e6"  # pragma: allowlist secret - Alembic revision
_REVISION = "a6b8c0d2e4f7"  # pragma: allowlist secret - Alembic revision


def test_session_version_upgrade_and_downgrade(db_url):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PREVIOUS_REVISION)
    engine = create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    'INSERT INTO "user" (id, username, password, is_active, is_superuser, create_at, updated_at) '
                    "VALUES ('12345678123456781234567812345678', 'legacy-session-user', 'existing-hash', "
                    "true, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
        command.upgrade(config, _REVISION)
        with engine.connect() as connection:
            column = next(c for c in inspect(connection).get_columns("user") if c["name"] == "session_version")
            assert column["nullable"] is True
            assert connection.execute(
                text("SELECT password, session_version FROM \"user\" WHERE username = 'legacy-session-user'")
            ).one() == ("existing-hash", None)
        command.downgrade(config, _PREVIOUS_REVISION)
        with engine.connect() as connection:
            assert "session_version" not in {c["name"] for c in inspect(connection).get_columns("user")}
            assert connection.execute(text('SELECT password FROM "user"')).scalar_one() == "existing-hash"
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(
                    text(
                        'INSERT INTO "user" (id, username, password, is_active, is_superuser, create_at, updated_at) '
                        "VALUES ('87654321876543218765432187654321', 'LEGACY-SESSION-USER', 'existing-hash', "
                        "true, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    )
                )
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE "user" ADD COLUMN session_version VARCHAR(64)'))
        command.upgrade(config, _REVISION)
    finally:
        engine.dispose()
