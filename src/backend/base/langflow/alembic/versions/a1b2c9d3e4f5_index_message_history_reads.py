"""Index the message columns every history read filters and sorts on.

Revision ID: a1b2c9d3e4f5
Revises: d7e9f1a3b5c8
Create Date: 2026-09-14

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "a1b2c9d3e4f5"  # pragma: allowlist secret
down_revision: str | None = "d7e9f1a3b5c8"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ``id`` trails the sort key: it is the paging tie-breaker, and without it in the
# index the planner sorts the matched rows instead of walking the index in order.
_INDEXES = (
    ("ix_message_flow_id_timestamp_id", ["flow_id", "timestamp", "id"]),
    ("ix_message_session_id_timestamp_id", ["session_id", "timestamp", "id"]),
)


def _existing_index_names(conn) -> set[str]:
    return {index["name"] for index in sa.inspect(conn).get_indexes("message")}


def _invalid_postgres_indexes(conn, names: set[str]) -> set[str]:
    """Names among ``names`` that Postgres left INVALID after a failed concurrent build.

    A cancelled ``CREATE INDEX CONCURRENTLY`` leaves the index in place but unusable,
    and it still shows up in the inspector. Without this the retry would consider the
    index present and skip it, leaving a dead index the planner never uses.
    """
    if not names:
        return set()
    rows = conn.execute(
        sa.text(
            "SELECT c.relname FROM pg_class c "
            "JOIN pg_index i ON i.indexrelid = c.oid "
            "WHERE NOT i.indisvalid AND c.relname = ANY(:names)"
        ),
        {"names": sorted(names)},
    )
    return {row[0] for row in rows}


def upgrade() -> None:
    """Add the read-path indexes without blocking writes on a large message table."""
    conn = op.get_bind()
    if not migration.table_exists("message", conn):
        return
    is_postgres = conn.dialect.name == "postgresql"
    existing = _existing_index_names(conn)

    if is_postgres:
        invalid = _invalid_postgres_indexes(conn, existing & {name for name, _ in _INDEXES})
        if invalid:
            # Drop before rebuilding, otherwise the name is taken by a dead index.
            with op.get_context().autocommit_block():
                for name in sorted(invalid):
                    op.drop_index(name, table_name="message", postgresql_concurrently=True)
            existing -= invalid

    missing = [(name, columns) for name, columns in _INDEXES if name not in existing]
    if not missing:
        return

    if is_postgres:
        # A plain CREATE INDEX holds a write lock for the whole build. Deployments roll
        # pods, so an old pod is still writing messages while the new one migrates —
        # that lock would stall it. CONCURRENTLY cannot run in the migration transaction.
        with op.get_context().autocommit_block():
            for name, columns in missing:
                op.create_index(name, "message", columns, postgresql_concurrently=True)
    else:
        for name, columns in missing:
            op.create_index(name, "message", columns)


def downgrade() -> None:
    """Drop the read-path indexes, leaving message rows untouched."""
    conn = op.get_bind()
    if not migration.table_exists("message", conn):
        return
    present = [name for name, _ in _INDEXES if name in _existing_index_names(conn)]
    if not present:
        return

    if conn.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            for name in present:
                op.drop_index(name, table_name="message", postgresql_concurrently=True)
    else:
        for name in present:
            op.drop_index(name, table_name="message")
