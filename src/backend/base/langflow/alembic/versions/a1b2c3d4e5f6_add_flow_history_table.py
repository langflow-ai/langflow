"""add flow_history table and state columns to flow

Revision ID: a1b2c3d4e5f6
Revises: 369268b9af8b
Create Date: 2026-02-22 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "369268b9af8b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create flow_state_enum type
    flow_state_enum = sa.Enum("DRAFT", "PUBLISHED", "ARCHIVED", name="flow_state_enum")
    flow_state_enum.create(conn, checkfirst=True)

    # Create flow_history table
    if not migration.table_exists("flow_history", conn):
        op.create_table(
            "flow_history",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("flow_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("data", sa.JSON(), nullable=True),
            sa.Column("state", flow_state_enum, server_default=sa.text("'DRAFT'"), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["flow_id"], ["flow.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("flow_id", "version_number", name="unique_flow_version_number"),
        )
        op.create_index(op.f("ix_flow_history_flow_id"), "flow_history", ["flow_id"])
        op.create_index(op.f("ix_flow_history_user_id"), "flow_history", ["user_id"])

    # Add state column to flow table
    with op.batch_alter_table("flow", schema=None) as batch_op:
        if not migration.column_exists(table_name="flow", column_name="state", conn=conn):
            batch_op.add_column(
                sa.Column("state", flow_state_enum, server_default=sa.text("'DRAFT'"), nullable=False)
            )
        if not migration.column_exists(table_name="flow", column_name="active_version_id", conn=conn):
            batch_op.add_column(sa.Column("active_version_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()

    with op.batch_alter_table("flow", schema=None) as batch_op:
        if migration.column_exists(table_name="flow", column_name="active_version_id", conn=conn):
            batch_op.drop_column("active_version_id")
        if migration.column_exists(table_name="flow", column_name="state", conn=conn):
            batch_op.drop_column("state")

    if migration.table_exists("flow_history", conn):
        op.drop_index(op.f("ix_flow_history_user_id"), table_name="flow_history")
        op.drop_index(op.f("ix_flow_history_flow_id"), table_name="flow_history")
        op.drop_table("flow_history")

    flow_state_enum = sa.Enum("DRAFT", "PUBLISHED", "ARCHIVED", name="flow_state_enum")
    flow_state_enum.drop(conn, checkfirst=True)
