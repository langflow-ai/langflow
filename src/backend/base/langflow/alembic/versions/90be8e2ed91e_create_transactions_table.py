"""create transactions table

Revision ID: 90be8e2ed91e
Revises: 325180f0c4e1
Create Date: 2024-07-24 11:37:48.532933

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "90be8e2ed91e"
down_revision: str | None = "325180f0c4e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("transaction", conn):
        op.create_table(
            "transaction",
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("vertex_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("target_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("inputs", sa.JSON(), nullable=True),
            sa.Column("outputs", sa.JSON(), nullable=True),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("flow_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.ForeignKeyConstraint(
                ["flow_id"],
                ["flow.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists("transaction", conn):
        op.drop_table("transaction")
