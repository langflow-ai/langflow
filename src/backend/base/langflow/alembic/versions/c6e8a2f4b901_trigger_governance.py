"""Add optional trigger policy to immutable bundle revisions.

Revision ID: c6e8a2f4b901
Revises: f6a2c8e4b901
Create Date: 2026-11-10

Phase: EXPAND

Existing revisions retain an unrestricted NULL trigger facet and their original
content hashes. Enable a trigger ceiling only after every replica supports it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "c6e8a2f4b901"  # pragma: allowlist secret
down_revision: str | None = "f6a2c8e4b901"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists("policy_bundle_revision", conn) and not migration.column_exists(
        "policy_bundle_revision", "approved_trigger_kinds", conn
    ):
        op.add_column("policy_bundle_revision", sa.Column("approved_trigger_kinds", sa.JSON(), nullable=True))
    if not migration.table_exists("trigger_renewal_observation", conn):
        op.create_table(
            "trigger_renewal_observation",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("trigger_id", sa.Uuid(), sa.ForeignKey("trigger.id", ondelete="CASCADE"), nullable=False),
            sa.Column("subscription_id", sa.Uuid(), nullable=False),
            sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("previous_expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("outcome", sa.String(16), nullable=False),
            sa.Column("gap_seconds", sa.Float(), nullable=False),
            sa.CheckConstraint("outcome IN ('renewed', 'failed')", name=op.f("ck_trigger_renewal_outcome")),
            sa.CheckConstraint("gap_seconds >= 0", name=op.f("ck_trigger_renewal_gap_nonnegative")),
        )
        op.create_index("ix_trigger_renewal_observation_observed_at", "trigger_renewal_observation", ["observed_at"])
        op.create_index("ix_trigger_renewal_observation_trigger_id", "trigger_renewal_observation", ["trigger_id"])


def downgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists("trigger_renewal_observation", conn):
        op.drop_table("trigger_renewal_observation")
    if migration.table_exists("policy_bundle_revision", conn) and migration.column_exists(
        "policy_bundle_revision", "approved_trigger_kinds", conn
    ):
        with op.batch_alter_table("policy_bundle_revision") as batch:
            batch.drop_column("approved_trigger_kinds")
