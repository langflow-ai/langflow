"""Add durable project replacement receipts.

Revision ID: f194a1b2c3d4
Revises: f9d3b7a5c201
Create Date: 2026-09-21

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "f194a1b2c3d4"  # pragma: allowlist secret -- migration revision identifier
down_revision: str | None = "f9d3b7a5c201"  # pragma: allowlist secret -- migration revision identifier
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("project_replacement_operation", conn):
        op.create_table(
            "project_replacement_operation",
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("operation_id", sa.Uuid(), nullable=False),
            sa.Column("request_digest", sa.String(length=64), nullable=False),
            # Nullable: a pruned receipt is tombstoned (result cleared) rather than
            # deleted, so a retry against it can 410 instead of silently replaying.
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("project_user_id", sa.Uuid(), nullable=True),
            sa.Column("workspace_id", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("project_id", "operation_id", name="pk_project_replacement_operation"),
        )
    else:
        expected_columns = {
            "project_id",
            "operation_id",
            "request_digest",
            "result",
            "project_user_id",
            "workspace_id",
            "created_at",
        }
        missing_columns = {
            column
            for column in expected_columns
            if not migration.column_exists("project_replacement_operation", column, conn)
        }
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            message = f"Existing 'project_replacement_operation' table is missing columns: {missing}"
            raise RuntimeError(message)


def downgrade() -> None:
    op.drop_table("project_replacement_operation")
