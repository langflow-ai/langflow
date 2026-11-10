"""Retain trigger source versions across event-ledger purges.

Revision ID: a7c9e4b681f2
Revises: f2a7c9e4b681

Phase: EXPAND
Safe to rollback: YES
Services compatible: Versions that do not read trigger_source_version
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7c9e4b681f2"  # pragma: allowlist secret
down_revision = "f2a7c9e4b681"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("trigger_source_version"):
        # The test harness initializes SQLModel metadata before running the
        # migration; a real pre-upgrade database has no such table.
        return
    op.create_table(
        "trigger_source_version",
        sa.Column("trigger_id", sa.Uuid(), nullable=False),
        sa.Column("item_key", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("resource", sa.String(length=512), nullable=False),
        sa.Column("provider_item_id", sa.String(length=512), nullable=False),
        sa.Column("version", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["trigger_id"], ["trigger.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("trigger_id", "item_key"),
    )


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("trigger_source_version"):
        op.drop_table("trigger_source_version")
