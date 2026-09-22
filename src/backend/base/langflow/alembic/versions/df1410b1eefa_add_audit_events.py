"""Add the append-only audit_events table.

Revision ID: df1410b1eefa
Revises: 9d7e2a6c4b81
Create Date: 2026-09-15

Phase: EXPAND

Additive only: one new table with no foreign keys, so no existing row is read,
rewritten or constrained. Rolling back drops the audit history and nothing else.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision = "df1410b1eefa"  # pragma: allowlist secret
down_revision = "9d7e2a6c4b81"  # pragma: allowlist secret
branch_labels = None
depends_on = None

TABLE = "audit_events"
INDEXES = (
    ("ix_audit_events_resource_timeline", ["resource_type", "resource_id", "timestamp", "id"]),
    ("ix_audit_events_type_timeline", ["resource_type", "timestamp", "id"]),
    ("ix_audit_events_user_timeline", ["user_id", "timestamp"]),
    ("ix_audit_events_actor_timeline", ["actor_type", "actor_id", "timestamp"]),
    ("ix_audit_events_acting_timeline", ["acting_issuer", "acting_subject", "timestamp"]),
    ("ix_audit_events_request_id", ["request_id"]),
)


def _database_clock_default() -> sa.TextClause:
    """Render the same wall-clock default used by the runtime model."""
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        return sa.text("((STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW') || '000'))")
    if dialect == "postgresql":
        return sa.text("clock_timestamp()")
    return sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    if migration.table_exists(TABLE, op.get_bind()):
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("resource_name", sa.String(255), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("acting_issuer", sa.String(2048), nullable=True),
        sa.Column("acting_subject", sa.String(512), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(16), nullable=False),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=_database_clock_default(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(event_type = 'authz' AND result IN ('allow', 'deny')) "
            "OR (event_type = 'action' AND result IN ('succeeded', 'failed'))",
            name=op.f("ck_audit_events_event_type_result"),
        ),
        sa.CheckConstraint(
            "(acting_issuer IS NULL AND acting_subject IS NULL) "
            "OR (acting_issuer IS NOT NULL AND acting_subject IS NOT NULL)",
            name=op.f("ck_audit_events_acting_pair"),
        ),
    )
    for name, columns in INDEXES:
        op.create_index(name, TABLE, columns)


def downgrade() -> None:
    if not migration.table_exists(TABLE, op.get_bind()):
        return
    for name, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=TABLE)
    op.drop_table(TABLE)
