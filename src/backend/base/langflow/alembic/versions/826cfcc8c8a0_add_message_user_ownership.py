"""Add nullable message ownership for tenant-scoped chat history.

Revision ID: 826cfcc8c8a0
Revises: e1705947c729
Create Date: 2026-07-14 00:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils.migration import column_exists, table_exists

revision: str = "826cfcc8c8a0"  # pragma: allowlist secret
down_revision: str | None = "e1705947c729"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if not table_exists("message", conn) or column_exists("message", "user_id", conn):
        return
    with op.batch_alter_table("message", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Uuid(), nullable=True))
        batch_op.create_index("ix_message_user_id", ["user_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    if not table_exists("message", conn) or not column_exists("message", "user_id", conn):
        return
    with op.batch_alter_table("message", schema=None) as batch_op:
        batch_op.drop_index("ix_message_user_id")
        batch_op.drop_column("user_id")
