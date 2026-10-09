"""Index messages by flow and session so session lists avoid scanning the table.

Revision ID: c4d8e2f6a1b7
Revises: d4f1a6c8e2b7
Create Date: 2026-09-18

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "c4d8e2f6a1b7"  # pragma: allowlist secret
down_revision: str | None = "d4f1a6c8e2b7"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Session lists group a flow's messages by session_id and take MAX(timestamp);
# covering all three columns lets Postgres answer that with an index-only scan.
_INDEX_NAME = "ix_message_flow_id_session_id_timestamp"
_INDEX_COLUMNS = ["flow_id", "session_id", "timestamp"]


def _index_exists(conn) -> bool:
    return _INDEX_NAME in {index["name"] for index in sa.inspect(conn).get_indexes("message")}


def _index_is_invalid_postgres(conn) -> bool:
    """Whether Postgres left the index INVALID after a failed concurrent build.

    A cancelled ``CREATE INDEX CONCURRENTLY`` leaves the index in place but unusable,
    and it still shows up in the inspector. Without this the retry would consider the
    index present and skip it, leaving a dead index the planner never uses.
    """
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_class c "
            "JOIN pg_index i ON i.indexrelid = c.oid "
            "WHERE i.indrelid = 'message'::regclass AND NOT i.indisvalid AND c.relname = :name"
        ),
        {"name": _INDEX_NAME},
    ).first()
    return row is not None


def upgrade() -> None:
    """Add the session-list index without blocking writes on a large message table."""
    conn = op.get_bind()
    if not migration.table_exists("message", conn):
        return
    is_postgres = conn.dialect.name == "postgresql"
    exists = _index_exists(conn)

    if exists and is_postgres and _index_is_invalid_postgres(conn):
        # Drop before rebuilding, otherwise the name is taken by a dead index.
        with op.get_context().autocommit_block():
            op.drop_index(_INDEX_NAME, table_name="message", postgresql_concurrently=True)
        exists = False
    if exists:
        return

    if is_postgres:
        # A plain CREATE INDEX holds a write lock for the whole build. Deployments roll
        # pods, so an old pod is still writing messages while the new one migrates —
        # that lock would stall it. CONCURRENTLY cannot run in the migration transaction.
        with op.get_context().autocommit_block():
            op.create_index(_INDEX_NAME, "message", _INDEX_COLUMNS, postgresql_concurrently=True)
    else:
        op.create_index(_INDEX_NAME, "message", _INDEX_COLUMNS)


def downgrade() -> None:
    """Drop the session-list index, leaving message rows untouched."""
    conn = op.get_bind()
    if not migration.table_exists("message", conn) or not _index_exists(conn):
        return

    if conn.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.drop_index(_INDEX_NAME, table_name="message", postgresql_concurrently=True)
    else:
        op.drop_index(_INDEX_NAME, table_name="message")
