"""add agent table

Revision ID: a1b2c3d4e5f6
Revises: 3478f0bd6ccb
Create Date: 2026-03-03 00:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "3478f0bd6ccb"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "agent" not in existing_tables:
        op.create_table(
            "agent",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False, index=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("system_prompt", sa.Text(), nullable=False),
            sa.Column("tool_components", sa.JSON(), nullable=False),
            sa.Column("icon", sa.String(length=255), nullable=True),
            sa.Column("user_id", sa.Uuid(), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "agent" in existing_tables:
        op.drop_table("agent")
