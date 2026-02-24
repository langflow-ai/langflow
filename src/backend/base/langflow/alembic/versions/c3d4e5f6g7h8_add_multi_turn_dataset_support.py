"""Add multi-turn dataset support

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2025-02-05 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6g7h8"
down_revision: str | None = "b2c3d4e5f6g7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Add dataset_type column to dataset table
    if not migration.column_exists("dataset", "dataset_type", conn):
        op.add_column(
            "dataset",
            sa.Column(
                "dataset_type",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default="single_turn",
            ),
        )

    # Add conversation_id column to datasetitem table
    if not migration.column_exists("datasetitem", "conversation_id", conn):
        op.add_column(
            "datasetitem",
            sa.Column(
                "conversation_id",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=True,
            ),
        )

    # Add conversation_id column to evaluationresult table
    if not migration.column_exists("evaluationresult", "conversation_id", conn):
        op.add_column(
            "evaluationresult",
            sa.Column(
                "conversation_id",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()

    if migration.column_exists("evaluationresult", "conversation_id", conn):
        op.drop_column("evaluationresult", "conversation_id")

    if migration.column_exists("datasetitem", "conversation_id", conn):
        op.drop_column("datasetitem", "conversation_id")

    if migration.column_exists("dataset", "dataset_type", conn):
        op.drop_column("dataset", "dataset_type")
