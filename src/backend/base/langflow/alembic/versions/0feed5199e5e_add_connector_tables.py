"""add connector tables

Revision ID: 0feed5199e5e
Revises: 182e5471b900
Create Date: 2025-10-27 17:06:51.037387

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "0feed5199e5e"  # pragma: allowlist secret
down_revision: str | None = "182e5471b900"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create connector_connections table
    if not migration.table_exists("connector_connections", conn):
        op.create_table(
            "connector_connections",
            sa.Column("id", sqlmodel.Uuid(), nullable=False),
            sa.Column("user_id", sqlmodel.Uuid(), nullable=False),
            sa.Column("knowledge_base_id", sa.String(255), nullable=True),
            sa.Column("connector_type", sa.String(50), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("config", sa.JSON(), nullable=False),
            sa.Column("webhook_subscription_id", sa.String(255), nullable=True),
            sa.Column("webhook_secret", sa.String(255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sync_status", sa.String(50), nullable=True),
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
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["user.id"],
                name="fk_connector_connections_user_id",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "knowledge_base_id",
                "connector_type",
                "name",
                name="uq_connector_connections_user_kb_type_name",
            ),
        )
        op.create_index("ix_connector_connections_user_id", "connector_connections", ["user_id"])
        op.create_index(
            "ix_connector_connections_knowledge_base_id",
            "connector_connections",
            ["knowledge_base_id"],
        )
        op.create_index(
            "ix_connector_connections_connector_type",
            "connector_connections",
            ["connector_type"],
        )

    # Create connector_oauth_tokens table
    if not migration.table_exists("connector_oauth_tokens", conn):
        op.create_table(
            "connector_oauth_tokens",
            sa.Column("id", sqlmodel.Uuid(), nullable=False),
            sa.Column("connection_id", sqlmodel.Uuid(), nullable=False),
            sa.Column("encrypted_access_token", sa.Text(), nullable=False),
            sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
            sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=True),
            sa.Column("scopes", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("provider_account_id", sa.String(255), nullable=True),
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
            sa.ForeignKeyConstraint(
                ["connection_id"],
                ["connector_connections.id"],
                name="fk_connector_oauth_tokens_connection_id",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("connection_id", name="uq_connector_oauth_tokens_connection_id"),
        )

    # Create connector_sync_logs table
    if not migration.table_exists("connector_sync_logs", conn):
        op.create_table(
            "connector_sync_logs",
            sa.Column("id", sqlmodel.Uuid(), nullable=False),
            sa.Column("connection_id", sqlmodel.Uuid(), nullable=False),
            sa.Column("sync_type", sa.String(50), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
            sa.Column("files_processed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("files_failed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("checkpoint", sa.JSON(), nullable=True),
            sa.Column("page_token", sa.String(500), nullable=True),
            sa.ForeignKeyConstraint(
                ["connection_id"],
                ["connector_connections.id"],
                name="fk_connector_sync_logs_connection_id",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_connector_sync_logs_connection_id",
            "connector_sync_logs",
            ["connection_id"],
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Drop tables in reverse order (respecting foreign key dependencies)
    if migration.table_exists("connector_sync_logs", conn):
        op.drop_table("connector_sync_logs")

    if migration.table_exists("connector_oauth_tokens", conn):
        op.drop_table("connector_oauth_tokens")

    if migration.table_exists("connector_connections", conn):
        op.drop_table("connector_connections")
