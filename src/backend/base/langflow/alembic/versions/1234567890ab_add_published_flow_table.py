"""add published flow table

Revision ID: 1234567890ab
Revises: 0a08019dc5cc
Create Date: 2025-01-21 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "1234567890ab"
down_revision: Union[str, None] = "0a08019dc5cc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create published_flow table for marketplace functionality."""
    conn = op.get_bind()

    if not migration.table_exists("published_flow", conn):
        op.create_table(
            "published_flow",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("flow_id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("published_by", sa.UUID(), nullable=False),
            sa.Column("status", sa.Enum('PUBLISHED', 'UNPUBLISHED', name='publish_status_enum'), nullable=False, server_default=sa.text("'PUBLISHED'")),
            sa.Column("version", sa.String(length=50), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("category", sa.String(length=100), nullable=True),
            sa.Column("flow_data", sa.JSON(), nullable=False),
            sa.Column("published_at", sa.DateTime(), nullable=False),
            sa.Column("unpublished_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["flow_id"],
                ["flow.id"],
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["user.id"],
            ),
            sa.ForeignKeyConstraint(
                ["published_by"],
                ["user.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("flow_id", name="uq_published_flow_flow_id"),
        )

        # Create indexes
        op.create_index("ix_published_flow_flow_id", "published_flow", ["flow_id"])
        op.create_index("ix_published_flow_user_id", "published_flow", ["user_id"])
        op.create_index("ix_published_flow_status", "published_flow", ["status"])
        op.create_index("ix_published_flow_category", "published_flow", ["category"])
        op.create_index("ix_published_flow_published_at", "published_flow", ["published_at"])


def downgrade() -> None:
    """Drop published_flow table."""
    conn = op.get_bind()

    if migration.table_exists("published_flow", conn):
        # Drop indexes
        op.drop_index("ix_published_flow_published_at", table_name="published_flow")
        op.drop_index("ix_published_flow_category", table_name="published_flow")
        op.drop_index("ix_published_flow_status", table_name="published_flow")
        op.drop_index("ix_published_flow_user_id", table_name="published_flow")
        op.drop_index("ix_published_flow_flow_id", table_name="published_flow")

        # Drop table (ENUM type is automatically dropped by SQLAlchemy)
        op.drop_table("published_flow")
