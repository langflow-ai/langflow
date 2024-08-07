"""Create vertex_builds table

Revision ID: 0d60fcbd4e8e
Revises: 90be8e2ed91e
Create Date: 2024-07-26 11:41:31.274271
"""

from typing import Optional, Sequence

from alembic import op
import sqlalchemy as sa
import sqlmodel
from langflow.utils import migration


# Revision identifiers, used by Alembic.
revision: str = "0d60fcbd4e8e"
down_revision: Optional[str] = "90be8e2ed91e"
branch_labels: Optional[Sequence[str]] = None
depends_on: Optional[Sequence[str]] = None


def upgrade() -> None:
    """Create the vertex_build table if it doesn't exist."""
    conn = op.get_bind()
    if not migration.table_exists("vertex_build", conn):
        op.create_table(
            "vertex_build",
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("data", sa.JSON(), nullable=True),
            sa.Column("artifacts", sa.JSON(), nullable=True),
            sa.Column("params", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("build_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
            sa.Column("flow_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
            sa.Column("valid", sa.BOOLEAN(), nullable=False),
            sa.ForeignKeyConstraint(
                ["flow_id"],
                ["flow.id"],
                name="fk_vertex_build_flow_id",
            ),
            sa.PrimaryKeyConstraint("build_id"),
        )


def downgrade() -> None:
    """Drop the vertex_build table if it exists."""
    conn = op.get_bind()
    if migration.table_exists("vertex_build", conn):
        op.drop_table("vertex_build")
