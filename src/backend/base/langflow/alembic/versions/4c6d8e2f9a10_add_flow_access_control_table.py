"""add flow access control table

Revision ID: 4c6d8e2f9a10
Revises: d306e5c17c41
Create Date: 2026-04-30 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "4c6d8e2f9a10"
down_revision: str | None = "d306e5c17c41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "flow_access_control"


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("flow_id", sa.Uuid(), nullable=False),
        sa.Column("subject_type", sa.String(length=16), nullable=False),
        sa.Column("subject_id", sa.String(length=255), nullable=False),
        sa.Column("permission", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "flow_id",
            "subject_type",
            "subject_id",
            "permission",
            name="unique_flow_access_control_entry",
        ),
    )
    op.create_index(op.f("ix_flow_access_control_flow_id"), TABLE_NAME, ["flow_id"])
    op.create_index(op.f("ix_flow_access_control_subject_type"), TABLE_NAME, ["subject_type"])
    op.create_index(op.f("ix_flow_access_control_subject_id"), TABLE_NAME, ["subject_id"])
    op.create_index(op.f("ix_flow_access_control_permission"), TABLE_NAME, ["permission"])


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    op.drop_index(op.f("ix_flow_access_control_permission"), table_name=TABLE_NAME)
    op.drop_index(op.f("ix_flow_access_control_subject_id"), table_name=TABLE_NAME)
    op.drop_index(op.f("ix_flow_access_control_subject_type"), table_name=TABLE_NAME)
    op.drop_index(op.f("ix_flow_access_control_flow_id"), table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
