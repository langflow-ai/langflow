"""Structure tests for the message history read-path indexes.

Runs on sqlite and (when configured) postgres.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from alembic import command
from sqlalchemy import create_engine, inspect, text

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

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
    command.downgrade(alembic_cfg, "a1b2c9d3e4f5")
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

    message_id = uuid.uuid4()
    engine = create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO message (id, timestamp, sender, sender_name, session_id, text,"
                    " files, error, edit, category, is_output)"
                    " VALUES (:id, :timestamp, 'User', 'User', 'witness-session', 'witness',"
                    " :files, :error, :edit, 'message', :is_output)"
                ),
                {
                    "id": message_id.hex if engine.dialect.name == "sqlite" else str(message_id),
                    "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc).replace(tzinfo=None),
                    "files": "[]",
                    "error": False,
                    "edit": False,
                    "is_output": False,
                },
            )

        command.downgrade(alembic_cfg, "d7e9f1a3b5c8")
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
