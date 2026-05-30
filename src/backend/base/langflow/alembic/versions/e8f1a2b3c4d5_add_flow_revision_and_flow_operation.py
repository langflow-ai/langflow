"""Add flow.latest_operation_revision for collaborative editing.

Phase: EXPAND
Revision ID: e8f1a2b3c4d5
Revises: c35e9db03a66
Create Date: 2026-05-28 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "e8f1a2b3c4d5"  # pragma: allowlist secret
down_revision: str | None = "c35e9db03a66"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    with op.batch_alter_table("flow", schema=None) as batch_op:
        if not migration.column_exists(table_name="flow", column_name="latest_operation_revision", conn=conn):
            batch_op.add_column(
                sa.Column("latest_operation_revision", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
            )
            batch_op.create_index(
                op.f("ix_flow_latest_operation_revision"),
                ["latest_operation_revision"],
                unique=False,
            )


def downgrade() -> None:
    conn = op.get_bind()

    with op.batch_alter_table("flow", schema=None) as batch_op:
        if migration.column_exists(table_name="flow", column_name="latest_operation_revision", conn=conn):
            batch_op.drop_index(op.f("ix_flow_latest_operation_revision"))
            batch_op.drop_column("latest_operation_revision")
