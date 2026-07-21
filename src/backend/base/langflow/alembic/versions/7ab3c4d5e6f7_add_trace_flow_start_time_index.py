"""Add composite index for trace list pagination.

Revision ID: 7ab3c4d5e6f7
Revises: 4f2a9c8d1e7b
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "7ab3c4d5e6f7"  # pragma: allowlist secret
down_revision: str | None = "4f2a9c8d1e7b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "trace"
INDEX_NAME = "ix_trace_flow_id_start_time"
OLD_INDEX_NAME = "ix_trace_flow_id"


def _index_exists(conn, index_name: str) -> bool:
    return index_name in {index["name"] for index in sa.inspect(conn).get_indexes(TABLE_NAME)}


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if not _index_exists(conn, INDEX_NAME):
        op.create_index(INDEX_NAME, TABLE_NAME, ["flow_id", "start_time"])
    if _index_exists(conn, OLD_INDEX_NAME):
        op.drop_index(OLD_INDEX_NAME, table_name=TABLE_NAME)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if not _index_exists(conn, OLD_INDEX_NAME):
        op.create_index(OLD_INDEX_NAME, TABLE_NAME, ["flow_id"])
    if _index_exists(conn, INDEX_NAME):
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
