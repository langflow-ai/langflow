"""Add connection metadata and encrypted credential tables.

Revision ID: f3b6a9d2e4c1
Revises: c9f2e5a7b1d4
Create Date: 2026-09-03

Phase: EXPAND
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "f3b6a9d2e4c1"  # pragma: allowlist secret
down_revision: str | None = "c9f2e5a7b1d4"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONNECTION_TABLE = "connection"
SECRET_TABLE = "connection_secret"  # noqa: S105  # pragma: allowlist secret - table name


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(CONNECTION_TABLE, conn):
        op.create_table(
            CONNECTION_TABLE,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("owner_id", sa.Uuid(), nullable=True),
            sa.Column("provider_key", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=False),
            sa.Column("ownership_mode", sa.String(length=16), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("health", sa.String(length=16), nullable=False),
            sa.Column("granted_scopes", sa.JSON(), nullable=False),
            sa.Column("executing_identity", sa.JSON(), nullable=False),
            sa.Column("allow_non_interactive", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("health_checked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint(
                "(ownership_mode = 'user' AND owner_id IS NOT NULL) OR "
                "(ownership_mode = 'instance' AND owner_id IS NULL)",
                name="ck_connection_owner_mode",
            ),
            sa.CheckConstraint(
                "status IN ('pending', 'ready', 'expired', 'revoked', 'error')",
                name="ck_connection_status",
            ),
            sa.CheckConstraint(
                "health IN ('unknown', 'healthy', 'unhealthy')",
                name="ck_connection_health",
            ),
            sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_connection_owner_id", CONNECTION_TABLE, ["owner_id"], unique=False)
        op.create_index(
            "uq_connection_user_provider_name",
            CONNECTION_TABLE,
            ["owner_id", "provider_key", "name"],
            unique=True,
            sqlite_where=sa.text("ownership_mode = 'user'"),
            postgresql_where=sa.text("ownership_mode = 'user'"),
        )
        op.create_index(
            "uq_connection_instance_provider_name",
            CONNECTION_TABLE,
            ["provider_key", "name"],
            unique=True,
            sqlite_where=sa.text("ownership_mode = 'instance'"),
            postgresql_where=sa.text("ownership_mode = 'instance'"),
        )

    if not migration.table_exists(SECRET_TABLE, conn):
        op.create_table(
            SECRET_TABLE,
            sa.Column("connection_id", sa.Uuid(), nullable=False),
            sa.Column("encrypted_payload", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["connection_id"], ["connection.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("connection_id"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(SECRET_TABLE, conn):
        op.drop_table(SECRET_TABLE)
    if migration.table_exists(CONNECTION_TABLE, conn):
        op.drop_index("uq_connection_instance_provider_name", table_name=CONNECTION_TABLE)
        op.drop_index("uq_connection_user_provider_name", table_name=CONNECTION_TABLE)
        op.drop_index("ix_connection_owner_id", table_name=CONNECTION_TABLE)
        op.drop_table(CONNECTION_TABLE)
