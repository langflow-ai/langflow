"""add retry fields to flowschedule

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-23 16:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "flowschedule" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("flowschedule")]
        if "retry_count" not in columns:
            op.add_column(
                "flowschedule",
                sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            )
        if "max_retries" not in columns:
            op.add_column(
                "flowschedule",
                sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "flowschedule" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("flowschedule")]
        if "max_retries" in columns:
            op.drop_column("flowschedule", "max_retries")
        if "retry_count" in columns:
            op.drop_column("flowschedule", "retry_count")
