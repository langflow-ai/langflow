"""add snapshot id to flow history deployment attachment

Revision ID: 2b9c4d8e7a11
Revises: 0f6a9f8b2d31
Create Date: 2026-02-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "2b9c4d8e7a11"
down_revision: str | None = "0f6a9f8b2d31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "flow_history_deployment_attachment"
COLUMN_NAME = "snapshot_id"
INDEX_NAME = "ix_flow_history_deployment_attachment_snapshot_id"


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.add_column(sa.Column(COLUMN_NAME, sa.String(), nullable=True))
        batch_op.create_index(INDEX_NAME, [COLUMN_NAME], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if not migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME)
        batch_op.drop_column(COLUMN_NAME)
