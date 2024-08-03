"""create vertex_builds table

Revision ID: 0d60fcbd4e8e
Revises: 90be8e2ed91e
Create Date: 2024-07-26 11:41:31.274271

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = "0d60fcbd4e8e"
down_revision: Union[str, None] = "90be8e2ed91e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
                "fk_vertex_build_flow_id",
            ),
            sa.PrimaryKeyConstraint("build_id"),
        )
    pass


def downgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists("vertex_build", conn):
        op.drop_table("vertex_build")
    pass
