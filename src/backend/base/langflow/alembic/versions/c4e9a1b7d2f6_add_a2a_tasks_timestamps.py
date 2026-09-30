"""add created_at/updated_at to a2a_tasks so the table can be pruned by age.

Revision ID: c4e9a1b7d2f6
Revises: a2c8f1e3b4d6
Create Date: 2026-07-03 10:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e9a1b7d2f6"  # pragma: allowlist secret
down_revision: str | None = "a2c8f1e3b4d6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    with op.batch_alter_table("a2a_tasks", schema=None) as batch_op:
        if not migration.column_exists(table_name="a2a_tasks", column_name="created_at", conn=conn):
            batch_op.add_column(
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True)
            )
        if not migration.column_exists(table_name="a2a_tasks", column_name="updated_at", conn=conn):
            batch_op.add_column(
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True)
            )


def downgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    with op.batch_alter_table("a2a_tasks", schema=None) as batch_op:
        if migration.column_exists(table_name="a2a_tasks", column_name="updated_at", conn=conn):
            batch_op.drop_column("updated_at")
        if migration.column_exists(table_name="a2a_tasks", column_name="created_at", conn=conn):
            batch_op.drop_column("created_at")
