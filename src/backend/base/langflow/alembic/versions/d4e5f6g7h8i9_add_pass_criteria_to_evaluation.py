"""Add pass criteria to evaluation

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2025-02-06 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "d4e5f6g7h8i9"
down_revision: str | None = "c3d4e5f6g7h8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Add pass_metric column to evaluation table
    if not migration.column_exists("evaluation", "pass_metric", conn):
        op.add_column(
            "evaluation",
            sa.Column(
                "pass_metric",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=True,
            ),
        )

    # Add pass_threshold column to evaluation table
    if not migration.column_exists("evaluation", "pass_threshold", conn):
        op.add_column(
            "evaluation",
            sa.Column(
                "pass_threshold",
                sa.Float(),
                nullable=False,
                server_default="0.5",
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()

    if migration.column_exists("evaluation", "pass_threshold", conn):
        op.drop_column("evaluation", "pass_threshold")

    if migration.column_exists("evaluation", "pass_metric", conn):
        op.drop_column("evaluation", "pass_metric")
