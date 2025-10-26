"""add flow_cloned_from and remove flow_data from published_flow

Revision ID: 20251024001858
Revises: 1234567890ab
Create Date: 2025-01-24 00:18:58.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "20251024001858"
down_revision: Union[str, None] = "1234567890ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add flow_cloned_from column and remove flow_data column."""
    conn = op.get_bind()

    if migration.table_exists("published_flow", conn):
        # 1. Add flow_cloned_from column (nullable initially)
        op.add_column(
            "published_flow", sa.Column("flow_cloned_from", sa.UUID(), nullable=True)
        )

        # 2. Add foreign key constraint
        op.create_foreign_key(
            "fk_published_flow_cloned_from",
            "published_flow",
            "flow",
            ["flow_cloned_from"],
            ["id"],
        )

        # 3. Add index on flow_cloned_from
        op.create_index(
            "ix_published_flow_flow_cloned_from",
            "published_flow",
            ["flow_cloned_from"],
        )

        # 4. Drop old unique constraint on flow_id
        op.drop_constraint(
            "uq_published_flow_flow_id", "published_flow", type_="unique"
        )

        # 5. Add unique constraint on flow_cloned_from
        op.create_unique_constraint(
            "uq_published_flow_cloned_from", "published_flow", ["flow_cloned_from"]
        )

        # 6. Remove flow_data column
        op.drop_column("published_flow", "flow_data")


def downgrade() -> None:
    """Reverse the changes - add back flow_data and remove flow_cloned_from."""
    conn = op.get_bind()

    if migration.table_exists("published_flow", conn):
        # Reverse all changes
        op.add_column(
            "published_flow", sa.Column("flow_data", sa.JSON(), nullable=False)
        )

        op.drop_constraint(
            "uq_published_flow_cloned_from", "published_flow", type_="unique"
        )

        op.create_unique_constraint(
            "uq_published_flow_flow_id", "published_flow", ["flow_id"]
        )

        op.drop_index("ix_published_flow_flow_cloned_from", table_name="published_flow")

        op.drop_constraint(
            "fk_published_flow_cloned_from", "published_flow", type_="foreignkey"
        )

        op.drop_column("published_flow", "flow_cloned_from")
