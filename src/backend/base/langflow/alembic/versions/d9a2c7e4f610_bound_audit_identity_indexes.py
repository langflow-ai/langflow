"""Bound audit identity indexes without changing stored identities.

Revision ID: d9a2c7e4f610
Revises: c8f3e6a2b901
Create Date: 2026-10-26

Phase: EXPAND

Index each subject and timestamp, leaving issuer equality filtering separate.
Replace oversized index shapes from earlier revisions and draft installations.
Keep every audit row and both full identity pairs.
"""

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision = "d9a2c7e4f610"  # pragma: allowlist secret
down_revision = "c8f3e6a2b901"  # pragma: allowlist secret
branch_labels = None
depends_on = None

TABLE = "audit_events"


def upgrade() -> None:
    """Repair both identity indexes, including an already-applied draft shape."""
    conn = op.get_bind()
    if not migration.table_exists(TABLE, conn):
        return
    indexes = {item["name"]: item for item in sa.inspect(conn).get_indexes(TABLE)}
    for prefix in ("acting", "represented"):
        name = f"ix_audit_events_{prefix}_timeline"
        columns = [f"{prefix}_subject", "timestamp"]
        existing = indexes.get(name)
        if existing is not None:
            if existing["column_names"] == columns:
                continue
            op.drop_index(name, table_name=TABLE)
        op.create_index(name, TABLE, columns)


def downgrade() -> None:
    """Keep safe indexes because older binaries can use the same stored rows."""
