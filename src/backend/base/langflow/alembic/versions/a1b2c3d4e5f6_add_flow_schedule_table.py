"""Add flow_schedule table for scheduled flow execution.

Revision ID: a1b2c3d4e5f6
Revises: 58b28437a398
Create Date: 2026-02-12 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "58b28437a398"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if not migration.table_exists("flow_schedule", conn):
        op.create_table(
            "flow_schedule",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("flow_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("cron_expression", sa.String(), nullable=False),
            sa.Column("timezone", sa.String(), nullable=False, server_default=sa.text("'UTC'")),
            sa.Column("days_of_week", sa.JSON(), nullable=True),
            sa.Column("times_of_day", sa.JSON(), nullable=True),
            sa.Column("repeat_frequency", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_run_status", sa.String(), nullable=True),
            sa.Column("last_run_error", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        )
        with op.batch_alter_table("flow_schedule", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_flow_schedule_flow_id"), ["flow_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_flow_schedule_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_flow_schedule_is_active"), ["is_active"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("flow_schedule", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_flow_schedule_is_active"))
        batch_op.drop_index(batch_op.f("ix_flow_schedule_user_id"))
        batch_op.drop_index(batch_op.f("ix_flow_schedule_flow_id"))

    op.drop_table("flow_schedule")
