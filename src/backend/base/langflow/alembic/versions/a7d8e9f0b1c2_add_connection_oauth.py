"""Add durable one-time OAuth consent bindings.

Revision ID: a7d8e9f0b1c2
Revises: f3b6a9d2e4c1
Create Date: 2026-09-04

Phase: EXPAND
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision = "a7d8e9f0b1c2"  # pragma: allowlist secret
down_revision = "f3b6a9d2e4c1"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not migration.table_exists("connection_oauth", op.get_bind()):
        op.create_table(
            "connection_oauth",
            sa.Column("connection_id", sa.Uuid(), nullable=False),
            sa.Column("generation", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("registration_id", sa.String(120), nullable=False),
            sa.Column("config_digest", sa.String(64), nullable=False),
            sa.Column("state_digest", sa.String(64), nullable=True),
            sa.Column("browser_digest", sa.String(64), nullable=True),
            sa.Column("encrypted_verifier", sa.Text(), nullable=True),
            sa.Column("scopes", sa.JSON(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["connection_id"], ["connection.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("connection_id"),
            sa.UniqueConstraint("state_digest"),
        )


def downgrade() -> None:
    if migration.table_exists("connection_oauth", op.get_bind()):
        op.drop_table("connection_oauth")
