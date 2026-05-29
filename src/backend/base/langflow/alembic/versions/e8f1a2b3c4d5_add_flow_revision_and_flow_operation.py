"""Add flow.latest_operation_revision and flow_operation table for collaborative editing.

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

    if not migration.table_exists("flow_operation", conn):
        op.create_table(
            "flow_operation",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("flow_id", sa.Uuid(), nullable=False),
            sa.Column("protocol_version", sa.Integer(), nullable=False),
            sa.Column("revision", sa.BigInteger(), nullable=False),
            sa.Column("client_id", sa.String(), nullable=False),
            sa.Column("actor_user_id", sa.Uuid(), nullable=True),
            sa.Column("actor_delegate", sa.String(), server_default="self", nullable=False),
            sa.Column("forward_ops", sa.JSON(), nullable=False),
            sa.Column("backward_ops", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("flow_id", "revision", name="unique_flow_operation_revision"),
        )
        op.create_index(op.f("ix_flow_operation_flow_id"), "flow_operation", ["flow_id"])
        op.create_index(op.f("ix_flow_operation_actor_user_id"), "flow_operation", ["actor_user_id"])
        op.create_index(
            "ix_flow_operation_flow_id_created_at",
            "flow_operation",
            ["flow_id", "created_at"],
        )


def downgrade() -> None:
    conn = op.get_bind()

    if migration.table_exists("flow_operation", conn):
        op.drop_index("ix_flow_operation_flow_id_created_at", table_name="flow_operation")
        op.drop_index(op.f("ix_flow_operation_actor_user_id"), table_name="flow_operation")
        op.drop_index(op.f("ix_flow_operation_flow_id"), table_name="flow_operation")
        op.drop_table("flow_operation")

    with op.batch_alter_table("flow", schema=None) as batch_op:
        if migration.column_exists(table_name="flow", column_name="latest_operation_revision", conn=conn):
            batch_op.drop_index(op.f("ix_flow_latest_operation_revision"))
            batch_op.drop_column("latest_operation_revision")
