"""add drafted column to published_flow_version

Revision ID: 20251107000000
Revises: 20251106000000
Create Date: 2025-11-07 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251107000000"
down_revision: Union[str, None] = "20251106000000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add drafted column to track currently viewed/edited version."""
    # Add drafted column with default False
    op.add_column(
        "published_flow_version",
        sa.Column("drafted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # Add partial unique index: ensures only one drafted version per original flow
    # This prevents multiple versions from being drafted simultaneously for the same flow
    op.create_index(
        "uq_published_flow_version_one_drafted",
        "published_flow_version",
        ["flow_id_cloned_from", "drafted"],
        unique=True,
        postgresql_where=sa.text("drafted = true"),
    )


def downgrade() -> None:
    """Remove drafted column and its index."""
    # Drop the unique index first
    op.drop_index(
        "uq_published_flow_version_one_drafted",
        table_name="published_flow_version",
    )

    # Drop the drafted column
    op.drop_column("published_flow_version", "drafted")
