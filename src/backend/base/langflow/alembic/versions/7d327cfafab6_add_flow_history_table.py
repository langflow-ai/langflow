"""add flow_version table

Revision ID: 7d327cfafab6
Revises: 3478f0bd6ccb
Create Date: 2026-02-22 00:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "7d327cfafab6"
down_revision: str | None = "3478f0bd6ccb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create flow_version table
    if not migration.table_exists("flow_version", conn):
        op.create_table(
            "flow_version",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("flow_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=True),
            sa.Column("data", sa.JSON(), nullable=True),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("flow_id", "version_number", name="unique_flow_version_number"),
            sa.CheckConstraint("version_number >= 1", name="check_version_number_positive"),
        )
        op.create_index(op.f("ix_flow_version_flow_id"), "flow_version", ["flow_id"])
        op.create_index(op.f("ix_flow_version_user_id"), "flow_version", ["user_id"])
        op.create_index(op.f("ix_flow_version_created_at"), "flow_version", ["created_at"])


def downgrade() -> None:
    conn = op.get_bind()

    if migration.table_exists("flow_version", conn):
        op.drop_index(op.f("ix_flow_version_created_at"), table_name="flow_version")
        op.drop_index(op.f("ix_flow_version_user_id"), table_name="flow_version")
        op.drop_index(op.f("ix_flow_version_flow_id"), table_name="flow_version")
        op.drop_table("flow_version")
