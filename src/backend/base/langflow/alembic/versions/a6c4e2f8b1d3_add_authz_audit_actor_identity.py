"""Add first-class actor identity to authorization audit rows.

Phase: EXPAND
Revision ID: a6c4e2f8b1d3
Revises: d19e7b3c5a42
Create Date: 2026-07-22 00:00:00.000000

Both columns are nullable for N-1 compatibility and to preserve legacy rows.
``actor_id`` intentionally has no foreign key: audit attribution must survive
deletion of an API key or other credential record.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
import sqlmodel
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "a6c4e2f8b1d3"  # pragma: allowlist secret
down_revision: str | None = "d19e7b3c5a42"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "authz_audit_log"
ACTOR_INDEX = "ix_authz_audit_log_actor_timestamp"
ACTOR_TYPE_INDEX = "ix_authz_audit_log_actor_type_timestamp"


def _index_exists(conn, index_name: str) -> bool:
    return index_name in {index["name"] for index in sa.inspect(conn).get_indexes(TABLE_NAME)}


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        if not migration.column_exists(TABLE_NAME, "actor_type", conn):
            batch_op.add_column(sa.Column("actor_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        if not migration.column_exists(TABLE_NAME, "actor_id", conn):
            batch_op.add_column(sa.Column("actor_id", sa.Uuid(), nullable=True))

    # Re-inspect after the batch because SQLite recreates the table.
    if not _index_exists(conn, ACTOR_INDEX):
        op.create_index(ACTOR_INDEX, TABLE_NAME, ["actor_id", "timestamp"], unique=False)
    if not _index_exists(conn, ACTOR_TYPE_INDEX):
        op.create_index(ACTOR_TYPE_INDEX, TABLE_NAME, ["actor_type", "timestamp"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    for index_name in (ACTOR_INDEX, ACTOR_TYPE_INDEX):
        if _index_exists(conn, index_name):
            op.drop_index(index_name, table_name=TABLE_NAME)

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        if migration.column_exists(TABLE_NAME, "actor_id", conn):
            batch_op.drop_column("actor_id")
        if migration.column_exists(TABLE_NAME, "actor_type", conn):
            batch_op.drop_column("actor_type")
