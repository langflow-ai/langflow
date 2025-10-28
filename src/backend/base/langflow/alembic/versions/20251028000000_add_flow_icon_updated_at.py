"""add flow_icon_updated_at column

Revision ID: 20251028000000
Revises: 20251027130000
Create Date: 2025-10-28 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = "20251028000000"
down_revision: Union[str, None] = "20251027130000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add flow_icon_updated_at column to track when agent logo was last updated."""
    conn = op.get_bind()
    inspector: Inspector = sa.inspect(conn)  # type: ignore
    table_names = inspector.get_table_names()

    # Add column if table exists
    if "published_flow" in table_names:
        with op.batch_alter_table("published_flow", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "flow_icon_updated_at",
                    sa.DateTime(),
                    nullable=True,
                )
            )


def downgrade() -> None:
    """Remove flow_icon_updated_at column."""
    with op.batch_alter_table("published_flow", schema=None) as batch_op:
        batch_op.drop_column("flow_icon_updated_at")