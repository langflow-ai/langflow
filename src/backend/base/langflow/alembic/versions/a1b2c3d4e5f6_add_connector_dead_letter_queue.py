"""add connector dead letter queue

Revision ID: a1b2c3d4e5f6
Revises: 0feed5199e5e
Create Date: 2025-10-28 21:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"  # pragma: allowlist secret
down_revision: str | None = "0feed5199e5e"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create connector_dead_letter_queue table
    if not migration.table_exists("connector_dead_letter_queue", conn):
        op.create_table(
            "connector_dead_letter_queue",
            sa.Column("id", sqlmodel.Uuid(), nullable=False),
            sa.Column("connection_id", sqlmodel.Uuid(), nullable=False),
            sa.Column("operation_type", sa.String(50), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("error_category", sa.String(50), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("error_details", sa.JSON(), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
            ),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["connection_id"],
                ["connector_connections.id"],
                name="fk_connector_dlq_connection_id",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_connector_dead_letter_queue_connection_id",
            "connector_dead_letter_queue",
            ["connection_id"],
        )


def downgrade() -> None:
    conn = op.get_bind()

    if migration.table_exists("connector_dead_letter_queue", conn):
        op.drop_table("connector_dead_letter_queue")
