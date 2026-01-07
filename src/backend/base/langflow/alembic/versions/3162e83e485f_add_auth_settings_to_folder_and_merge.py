"""Add auth_settings column to folder table and merge migration branches.

Revision ID: 3162e83e485f
Revises: 0ae3a2674f32, d9a6ea21edcd
Create Date: 2025-01-16 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3162e83e485f"
down_revision: str | Sequence[str] | None = ("0ae3a2674f32", "d9a6ea21edcd")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add auth_settings column to folder table and merge migration branches."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Check if folder table exists
    table_names = inspector.get_table_names()
    if "folder" not in table_names:
        # If folder table doesn't exist, skip this migration
        return

    # Get current column names in folder table
    column_names = [column["name"] for column in inspector.get_columns("folder")]

    # Add auth_settings column to folder table if it doesn't exist
    with op.batch_alter_table("folder", schema=None) as batch_op:
        if "auth_settings" not in column_names:
            batch_op.add_column(sa.Column("auth_settings", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove auth_settings column from folder table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Check if folder table exists
    table_names = inspector.get_table_names()
    if "folder" not in table_names:
        # If folder table doesn't exist, skip this migration
        return

    # Get current column names in folder table
    column_names = [column["name"] for column in inspector.get_columns("folder")]

    # Remove auth_settings column from folder table if it exists
    with op.batch_alter_table("folder", schema=None) as batch_op:
        if "auth_settings" in column_names:
            batch_op.drop_column("auth_settings")
