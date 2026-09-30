"""Persist remote trigger cleanup independently of deleted flow rows.

Revision ID: d7f1b5c9a203
Revises: b6e2d4f8a901
Phase: EXPAND
Safe to rollback: YES (finish outstanding cleanup before dropping its queue)
Services compatible: Older versions ignore this additional table.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "d7f1b5c9a203"  # pragma: allowlist secret - Alembic revision
down_revision = "b6e2d4f8a901"  # pragma: allowlist secret - Alembic revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("trigger_cleanup"):
        return
    op.create_table(
        "trigger_cleanup",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("trigger_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("provider_subscription_id", sa.String(255), nullable=False),
        sa.Column("provider_state", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(128), nullable=True),
    )
    op.create_index("ix_trigger_cleanup_available_at", "trigger_cleanup", ["available_at"])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("trigger_cleanup"):
        op.drop_table("trigger_cleanup")
