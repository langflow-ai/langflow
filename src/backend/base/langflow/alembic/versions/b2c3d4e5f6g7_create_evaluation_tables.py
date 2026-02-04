"""Create evaluation tables

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2025-02-04 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create evaluation table
    if not migration.table_exists("evaluation", conn):
        op.create_table(
            "evaluation",
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False, default="pending"),
            sa.Column("scoring_methods", sa.JSON(), nullable=True),
            sa.Column("user_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("dataset_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("flow_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("total_items", sa.Integer(), nullable=False, default=0),
            sa.Column("completed_items", sa.Integer(), nullable=False, default=0),
            sa.Column("passed_items", sa.Integer(), nullable=False, default=0),
            sa.Column("mean_score", sa.Float(), nullable=True),
            sa.Column("mean_duration_ms", sa.Float(), nullable=True),
            sa.Column("total_runtime_ms", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.ForeignKeyConstraint(["dataset_id"], ["dataset.id"]),
            sa.ForeignKeyConstraint(["flow_id"], ["flow.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    # Create evaluationresult table
    if not migration.table_exists("evaluationresult", conn):
        op.create_table(
            "evaluationresult",
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("evaluation_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("dataset_item_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=True),
            sa.Column("input", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("expected_output", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("actual_output", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("scores", sa.JSON(), nullable=True),
            sa.Column("passed", sa.Boolean(), nullable=False, default=False),
            sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("order", sa.Integer(), nullable=False, default=0),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.ForeignKeyConstraint(["evaluation_id"], ["evaluation.id"]),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Drop evaluationresult table first (due to FK constraint)
    if migration.table_exists("evaluationresult", conn):
        op.drop_table("evaluationresult")

    # Drop evaluation table
    if migration.table_exists("evaluation", conn):
        op.drop_table("evaluation")
