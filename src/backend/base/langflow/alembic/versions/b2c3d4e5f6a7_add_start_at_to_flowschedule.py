"""add start_at to flowschedule

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-23 12:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "flowschedule" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("flowschedule")]
        if "start_at" not in columns:
            op.add_column(
                "flowschedule",
                sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "flowschedule" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("flowschedule")]
        if "start_at" in columns:
            op.drop_column("flowschedule", "start_at")
