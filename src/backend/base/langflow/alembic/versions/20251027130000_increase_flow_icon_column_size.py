"""increase flow_icon column size

Revision ID: 20251027130000
Revises: 20251027120000
Create Date: 2025-10-27 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = "20251027130000"
down_revision: Union[str, None] = "20251027120000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Increase flow_icon column size from VARCHAR(255) to VARCHAR(1000) to support long Azure SAS URLs."""
    conn = op.get_bind()
    inspector: Inspector = sa.inspect(conn)  # type: ignore
    table_names = inspector.get_table_names()

    # Alter column if table exists
    if "published_flow" in table_names:
        with op.batch_alter_table("published_flow", schema=None) as batch_op:
            batch_op.alter_column(
                "flow_icon",
                existing_type=sa.VARCHAR(length=255),
                type_=sa.VARCHAR(length=1000),
                existing_nullable=True,
            )


def downgrade() -> None:
    """Revert flow_icon column size back to VARCHAR(255)."""
    with op.batch_alter_table("published_flow", schema=None) as batch_op:
        batch_op.alter_column(
            "flow_icon",
            existing_type=sa.VARCHAR(length=1000),
            type_=sa.VARCHAR(length=255),
            existing_nullable=True,
        )
