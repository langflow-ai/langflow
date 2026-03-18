"""add flow_version_deployment_attachment table and deployment_type column

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
revision: str = "c0d2ce43b315"  # pragma: allowlist secret
down_revision: str | None = "0e6138e7a0c2"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "flow_version_deployment_attachment"
DEPLOYMENT_TABLE = "deployment"
DEPLOYMENT_TYPE_COLUMN = "deployment_type"


def upgrade() -> None:
    conn = op.get_bind()

    if not migration.column_exists(DEPLOYMENT_TABLE, DEPLOYMENT_TYPE_COLUMN, conn):
        op.add_column(DEPLOYMENT_TABLE, sa.Column(DEPLOYMENT_TYPE_COLUMN, sa.String(), nullable=True))
        op.create_index(op.f("ix_deployment_deployment_type"), DEPLOYMENT_TABLE, [DEPLOYMENT_TYPE_COLUMN])

    if migration.table_exists(TABLE_NAME, conn):
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("flow_version_id", sa.Uuid(), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("provider_snapshot_id", sa.String(), nullable=True),
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
        sa.UniqueConstraint("flow_version_id", "deployment_id", name="uq_flow_version_deployment"),
    )
    op.create_index(op.f("ix_flow_version_deployment_attachment_user_id"), TABLE_NAME, ["user_id"])
    op.create_index(op.f("ix_flow_version_deployment_attachment_flow_version_id"), TABLE_NAME, ["flow_version_id"])
    op.create_index(op.f("ix_flow_version_deployment_attachment_deployment_id"), TABLE_NAME, ["deployment_id"])
    op.create_index(
        op.f("ix_flow_version_deployment_attachment_provider_snapshot_id"), TABLE_NAME, ["provider_snapshot_id"]
    )


def downgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        op.drop_index(op.f("ix_flow_version_deployment_attachment_provider_snapshot_id"), table_name=TABLE_NAME)
        op.drop_index(op.f("ix_flow_version_deployment_attachment_deployment_id"), table_name=TABLE_NAME)
        op.drop_index(op.f("ix_flow_version_deployment_attachment_flow_version_id"), table_name=TABLE_NAME)
        op.drop_index(op.f("ix_flow_version_deployment_attachment_user_id"), table_name=TABLE_NAME)
        op.drop_table(TABLE_NAME)

    if migration.column_exists(DEPLOYMENT_TABLE, DEPLOYMENT_TYPE_COLUMN, conn):
        op.drop_index(op.f("ix_deployment_deployment_type"), table_name=DEPLOYMENT_TABLE)
        op.drop_column(DEPLOYMENT_TABLE, DEPLOYMENT_TYPE_COLUMN)
