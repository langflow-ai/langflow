"""add mcp_server table

Revision ID: 247308ce2598
Revises: c3e7a1b9d2f4
Create Date: 2026-07-06 17:10:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "247308ce2598"  # pragma: allowlist secret
down_revision: str | None = "c3e7a1b9d2f4"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists("mcp_server", conn):
        return

    op.create_table(
        "mcp_server",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("transport", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_mcp_server_name_user"),
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("mcp_server", conn):
        return

    op.drop_table("mcp_server")
