"""add flow_version_deployment_attachment table

Revision ID: c0d2ce43b315
Revises: fc7f696a57bf
Create Date: 2026-03-09 00:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "c0d2ce43b315"
down_revision: str | None = "fc7f696a57bf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "flow_version_deployment_attachment"


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("flow_version_id", sa.Uuid(), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["flow_version_id"], ["flow_version.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_flow_version_deployment_attachment_user_id"), TABLE_NAME, ["user_id"])
    op.create_index(op.f("ix_flow_version_deployment_attachment_flow_version_id"), TABLE_NAME, ["flow_version_id"])
    op.create_index(op.f("ix_flow_version_deployment_attachment_deployment_id"), TABLE_NAME, ["deployment_id"])
    op.create_index(op.f("ix_flow_version_deployment_attachment_snapshot_id"), TABLE_NAME, ["snapshot_id"])


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    op.drop_index(op.f("ix_flow_version_deployment_attachment_snapshot_id"), table_name=TABLE_NAME)
    op.drop_index(op.f("ix_flow_version_deployment_attachment_deployment_id"), table_name=TABLE_NAME)
    op.drop_index(op.f("ix_flow_version_deployment_attachment_flow_version_id"), table_name=TABLE_NAME)
    op.drop_index(op.f("ix_flow_version_deployment_attachment_user_id"), table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
