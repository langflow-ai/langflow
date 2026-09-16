"""Structure tests for the message history read-path indexes.

Runs on sqlite and (when configured) postgres.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PREVIOUS_REVISION = "d7e9f1a3b5c8"  # pragma: allowlist secret
_EXPECTED_INDEXES = {
    "ix_message_flow_id_timestamp_id": ["flow_id", "timestamp", "id"],
    "ix_message_session_id_timestamp_id": ["session_id", "timestamp", "id"],
}


def _message_index_columns(connection) -> dict[str, list[str]]:
    return {
        index["name"]: list(index["column_names"])
        for index in inspect(connection).get_indexes("message")
        if index["name"] in _EXPECTED_INDEXES
    }


def _insert_witness(connection) -> None:
    message_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO message (id, timestamp, sender, sender_name, session_id, text,"
            " files, error, edit, category, is_output)"
            " VALUES (:id, :timestamp, 'User', 'User', 'witness-session', 'witness',"
            " :files, :error, :edit, 'message', :is_output)"
        ),
        {
            "id": message_id.hex if connection.dialect.name == "sqlite" else str(message_id),
            "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc).replace(tzinfo=None),
            "files": "[]",
            "error": False,
            "edit": False,
            "is_output": False,
        },
    )


def test_message_history_indexes_exist_at_head(db_url):  # noqa: F811
    """The read path must be indexed on the columns it filters and sorts by."""
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            assert _message_index_columns(connection) == _EXPECTED_INDEXES
    finally:
        engine.dispose()


def test_message_history_index_upgrade_is_idempotent(db_url):  # noqa: F811
    """Re-running the upgrade over existing indexes must not fail."""
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, "head")
    # Rewind only the version stamp, leaving the indexes present so upgrade
    # actually runs again and exercises its existing-index guards.
    command.stamp(alembic_cfg, _PREVIOUS_REVISION)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            assert _message_index_columns(connection) == _EXPECTED_INDEXES
    finally:
        engine.dispose()


def test_message_history_index_roundtrip_preserves_rows(db_url):  # noqa: F811
    """Downgrading and re-upgrading must only add and drop indexes, never rows."""
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            _insert_witness(connection)

        command.downgrade(alembic_cfg, _PREVIOUS_REVISION)
        with engine.connect() as connection:
            assert _message_index_columns(connection) == {}
            witness = connection.execute(
                text("SELECT text FROM message WHERE session_id = 'witness-session'")
            ).fetchall()
            assert [row[0] for row in witness] == ["witness"]

        command.upgrade(alembic_cfg, "head")
        with engine.connect() as connection:
            assert _message_index_columns(connection) == _EXPECTED_INDEXES
            witness = connection.execute(
                text("SELECT text FROM message WHERE session_id = 'witness-session'")
            ).fetchall()
            assert [row[0] for row in witness] == ["witness"]
    finally:
        engine.dispose()


def test_message_history_index_recovers_failed_concurrent_build(db_url):  # noqa: F811
    """A failed concurrent build must be replaced by a valid read-path index."""
    if not db_url.startswith("postgresql"):
        pytest.skip("Only PostgreSQL leaves invalid indexes after concurrent builds")
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(_engine_url(db_url), isolation_level="AUTOCOMMIT")
    validity = text("SELECT indisvalid FROM pg_index WHERE indexrelid = 'ix_message_session_id_timestamp_id'::regclass")
    try:
        with engine.connect() as connection:
            _insert_witness(connection)
            _insert_witness(connection)
            connection.execute(text("DROP INDEX CONCURRENTLY ix_message_session_id_timestamp_id"))
            # Duplicate session IDs make this real concurrent build fail and
            # leave the same unusable index state as an interrupted build.
            with pytest.raises(IntegrityError):
                connection.execute(
                    text("CREATE UNIQUE INDEX CONCURRENTLY ix_message_session_id_timestamp_id ON message (session_id)")
                )
            assert connection.execute(validity).scalar_one() is False

        command.stamp(alembic_cfg, _PREVIOUS_REVISION)
        command.upgrade(alembic_cfg, "head")
        with engine.connect() as connection:
            assert _message_index_columns(connection) == _EXPECTED_INDEXES
            assert connection.execute(validity).scalar_one() is True
            assert connection.execute(text("SELECT COUNT(*) FROM message")).scalar_one() == 2
    finally:
        engine.dispose()
