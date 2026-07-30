"""add flow_type and a2a columns to flow

Revision ID: 9f1d1d602aa3
Revises: a1f4c9d27b30
Create Date: 2026-06-25 12:26:09.624143

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "9f1d1d602aa3"  # pragma: allowlist secret
down_revision: str | None = "a1f4c9d27b30"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    flow_type_enum = sa.Enum("workflow", "agent", name="flow_type_enum")
    flow_type_enum.create(conn, checkfirst=True)
    with op.batch_alter_table("flow", schema=None) as batch_op:
        if not migration.column_exists(table_name="flow", column_name="flow_type", conn=conn):
            batch_op.add_column(
                sa.Column("flow_type", flow_type_enum, server_default=sa.text("'workflow'"), nullable=False)
            )
        if not migration.column_exists(table_name="flow", column_name="a2a_enabled", conn=conn):
            batch_op.add_column(sa.Column("a2a_enabled", sa.Boolean(), server_default=sa.false(), nullable=True))
        if not migration.column_exists(table_name="flow", column_name="a2a_card_overrides", conn=conn):
            batch_op.add_column(sa.Column("a2a_card_overrides", sa.JSON(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("flow", schema=None) as batch_op:
        if migration.column_exists(table_name="flow", column_name="a2a_card_overrides", conn=conn):
            batch_op.drop_column("a2a_card_overrides")
        if migration.column_exists(table_name="flow", column_name="a2a_enabled", conn=conn):
            batch_op.drop_column("a2a_enabled")
        if migration.column_exists(table_name="flow", column_name="flow_type", conn=conn):
            batch_op.drop_column("flow_type")

    flow_type_enum = sa.Enum("workflow", "agent", name="flow_type_enum")
    flow_type_enum.drop(conn, checkfirst=True)
