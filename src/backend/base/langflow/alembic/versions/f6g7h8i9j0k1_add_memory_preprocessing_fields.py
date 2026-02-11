"""Add memory preprocessing fields

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2025-02-09 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "f6g7h8i9j0k1"
down_revision: str | None = "e5f6g7h8i9j0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    if migration.table_exists("memory", conn):
        if not migration.column_exists("memory", "batch_size", conn):
            op.add_column("memory", sa.Column("batch_size", sa.Integer(), nullable=False, server_default="1"))
        if not migration.column_exists("memory", "preprocessing_enabled", conn):
            op.add_column(
                "memory",
                sa.Column("preprocessing_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            )
        if not migration.column_exists("memory", "preprocessing_model", conn):
            op.add_column(
                "memory",
                sa.Column("preprocessing_model", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            )
        if not migration.column_exists("memory", "preprocessing_prompt", conn):
            op.add_column(
                "memory",
                sa.Column("preprocessing_prompt", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            )
        if not migration.column_exists("memory", "pending_messages_count", conn):
            op.add_column(
                "memory",
                sa.Column("pending_messages_count", sa.Integer(), nullable=False, server_default="0"),
            )


def downgrade() -> None:
    conn = op.get_bind()

    if migration.table_exists("memory", conn):
        if migration.column_exists("memory", "pending_messages_count", conn):
            op.drop_column("memory", "pending_messages_count")
        if migration.column_exists("memory", "preprocessing_prompt", conn):
            op.drop_column("memory", "preprocessing_prompt")
        if migration.column_exists("memory", "preprocessing_model", conn):
            op.drop_column("memory", "preprocessing_model")
        if migration.column_exists("memory", "preprocessing_enabled", conn):
            op.drop_column("memory", "preprocessing_enabled")
        if migration.column_exists("memory", "batch_size", conn):
            op.drop_column("memory", "batch_size")
