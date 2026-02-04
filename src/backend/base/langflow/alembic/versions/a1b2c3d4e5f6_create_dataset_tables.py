"""Create dataset tables

Revision ID: a1b2c3d4e5f6
Revises: 23c16fac4a0d
Create Date: 2025-02-04 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "23c16fac4a0d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create dataset table
    if not migration.table_exists("dataset", conn):
        op.create_table(
            "dataset",
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("user_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "name", name="unique_dataset_name_per_user"),
        )
        op.create_index(op.f("ix_dataset_name"), "dataset", ["name"], unique=False)

    # Create datasetitem table
    if not migration.table_exists("datasetitem", conn):
        op.create_table(
            "datasetitem",
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("dataset_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("input", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("expected_output", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("order", sa.Integer(), nullable=False, default=0),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.ForeignKeyConstraint(["dataset_id"], ["dataset.id"]),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Drop datasetitem table first (due to FK constraint)
    if migration.table_exists("datasetitem", conn):
        op.drop_table("datasetitem")

    # Drop dataset table
    if migration.table_exists("dataset", conn):
        op.drop_index(op.f("ix_dataset_name"), table_name="dataset")
        op.drop_table("dataset")
