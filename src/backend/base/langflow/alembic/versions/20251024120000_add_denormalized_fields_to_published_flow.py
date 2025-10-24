"""add denormalized fields to published_flow

Revision ID: 20251024120000
Revises: 20251024001858
Create Date: 2025-01-24 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "20251024120000"
down_revision: Union[str, None] = "20251024001858"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add denormalized fields (flow_name, flow_icon, published_by_username) to published_flow."""
    conn = op.get_bind()

    if migration.table_exists("published_flow", conn):
        # Add denormalized fields
        op.add_column(
            "published_flow", sa.Column("flow_name", sa.String(length=255), nullable=True)
        )
        op.add_column(
            "published_flow", sa.Column("flow_icon", sa.String(length=255), nullable=True)
        )
        op.add_column(
            "published_flow", sa.Column("published_by_username", sa.String(length=255), nullable=True)
        )


def downgrade() -> None:
    """Remove denormalized fields from published_flow."""
    conn = op.get_bind()

    if migration.table_exists("published_flow", conn):
        op.drop_column("published_flow", "published_by_username")
        op.drop_column("published_flow", "flow_icon")
        op.drop_column("published_flow", "flow_name")
