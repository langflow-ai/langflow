"""add flow schedule table

Revision ID: a1b2c3d4e5f6
Revises: 0e6138e7a0c2, d37bc4322900, 1cb603706752
Create Date: 2026-03-22 10:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = ("0e6138e7a0c2", "d37bc4322900", "1cb603706752")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "flowschedule" not in existing_tables:
        op.create_table(
            "flowschedule",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("flow_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("schedule_type", sa.String(), nullable=False, server_default=sa.text("'cron'")),
            sa.Column("minute", sa.String(), nullable=False, server_default=sa.text("'0'")),
            sa.Column("hour", sa.String(), nullable=False, server_default=sa.text("'*'")),
            sa.Column("day_of_week", sa.String(), nullable=False, server_default=sa.text("'*'")),
            sa.Column("day_of_month", sa.String(), nullable=False, server_default=sa.text("'*'")),
            sa.Column("month", sa.String(), nullable=False, server_default=sa.text("'*'")),
            sa.Column("timezone", sa.String(), nullable=False, server_default=sa.text("'UTC'")),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_run_status", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("flow_id", name="unique_flow_schedule"),
        )
        op.create_index(op.f("ix_flowschedule_flow_id"), "flowschedule", ["flow_id"], unique=False)
        op.create_index(op.f("ix_flowschedule_user_id"), "flowschedule", ["user_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "flowschedule" in existing_tables:
        op.drop_index(op.f("ix_flowschedule_user_id"), table_name="flowschedule")
        op.drop_index(op.f("ix_flowschedule_flow_id"), table_name="flowschedule")
        op.drop_table("flowschedule")
