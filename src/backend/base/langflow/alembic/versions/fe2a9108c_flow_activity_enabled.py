"""add flow_activity_enabled column to flow

Phase: EXPAND

Revision ID: fe2a9108c1fb
Revises: mb00a1b2c3d4
Create Date: 2026-04-29 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "fe2a9108c1fb"  # pragma: allowlist secret
down_revision: str | None = "mb00a1b2c3d4"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("flow", schema=None) as batch_op:
        if not migration.column_exists(table_name="flow", column_name="flow_activity_enabled", conn=conn):
            batch_op.add_column(
                sa.Column(
                    "flow_activity_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("true"),
                )
            )


def downgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("flow", schema=None) as batch_op:
        if migration.column_exists(table_name="flow", column_name="flow_activity_enabled", conn=conn):
            batch_op.drop_column("flow_activity_enabled")
