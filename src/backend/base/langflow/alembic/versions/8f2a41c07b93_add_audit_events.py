"""add audit_events

Revision ID: 8f2a41c07b93
Revises: e8f0a2c4d6b9
Create Date: 2026-09-09

Phase: EXPAND

Additive only: a new table, no change to any existing one. Rolling back drops
the trail and nothing else.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "8f2a41c07b93"  # pragma: allowlist secret
down_revision: str | None = "e8f0a2c4d6b9"  # pragma: allowlist secret
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists("audit_events", conn):
        return

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("family", sa.String(), nullable=False),
        sa.Column("event", sa.String(), nullable=False),
        sa.Column("result", sa.String(), nullable=False),
        # No foreign key: attribution outlives the user it names, and a cascade
        # would erase the trail along with them.
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("family IN ('authz', 'action')", name="ck_audit_events_family"),
        sa.CheckConstraint(
            "result IN ('allow', 'deny', 'succeeded', 'failed')",
            name="ck_audit_events_result",
        ),
    )
    # Every index carries created_at last: a trail is always read newest-first,
    # and a filter without it still has to scan the matching rows to sort them.
    op.create_index("ix_audit_events_resource", "audit_events", ["resource_type", "resource_id", "created_at"])
    op.create_index("ix_audit_events_user", "audit_events", ["user_id", "created_at"])
    op.create_index("ix_audit_events_event", "audit_events", ["event", "created_at"])
    op.create_index("ix_audit_events_family_result", "audit_events", ["family", "result", "created_at"])


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("audit_events", conn):
        return
    op.drop_index("ix_audit_events_family_result", table_name="audit_events")
    op.drop_index("ix_audit_events_event", table_name="audit_events")
    op.drop_index("ix_audit_events_user", table_name="audit_events")
    op.drop_index("ix_audit_events_resource", table_name="audit_events")
    op.drop_table("audit_events")
