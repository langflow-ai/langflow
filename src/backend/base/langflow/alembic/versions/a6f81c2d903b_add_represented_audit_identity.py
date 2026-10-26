"""Add represented audit identity separately from authenticated acting identity.

Revision ID: a6f81c2d903b
Revises: 1d8d193028c8
Create Date: 2026-10-14

Phase: EXPAND

Keep acting columns, constraints and history unchanged. Represented columns
start null: acting identity cannot be used to infer represented identity.
Bound both identity indexes, including indexes left by draft installations.
Downgrade preserves the additive columns, safe indexes and all audit history.
"""

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision = "a6f81c2d903b"  # pragma: allowlist secret
down_revision = "1d8d193028c8"  # pragma: allowlist secret
branch_labels = None
depends_on = None

TABLE = "audit_events"
CHECK = "ck_audit_events_represented_pair"


def upgrade() -> None:
    """Add the migration changes without rewriting existing audit history."""
    conn = op.get_bind()
    if not migration.table_exists(TABLE, conn):
        return
    missing = [
        name for name in ("represented_issuer", "represented_subject") if not migration.column_exists(TABLE, name, conn)
    ]
    checks = {item["name"] for item in sa.inspect(conn).get_check_constraints(TABLE)}
    if missing or CHECK not in checks:
        with op.batch_alter_table(TABLE) as batch:
            for name in missing:
                batch.add_column(sa.Column(name, sa.String(2048 if name.endswith("issuer") else 512), nullable=True))
            if CHECK not in checks:
                batch.create_check_constraint(
                    op.f(CHECK),
                    "(represented_issuer IS NULL AND represented_subject IS NULL) "
                    "OR (represented_issuer IS NOT NULL AND represented_subject IS NOT NULL)",
                )
    indexes = {item["name"]: item for item in sa.inspect(conn).get_indexes(TABLE)}
    for prefix in ("acting", "represented"):
        name = f"ix_audit_events_{prefix}_timeline"
        columns = [f"{prefix}_subject", "timestamp"]
        existing = indexes.get(name)
        if existing is not None:
            if existing["column_names"] == columns:
                continue
            op.drop_index(name, table_name=TABLE)
        # A subject uses at most 2048 UTF-8 bytes. Keep the full issuer stored
        # and filtered separately so PostgreSQL's B-tree key limit is respected.
        op.create_index(name, TABLE, columns)


def downgrade() -> None:
    """Old binaries ignore the added columns; retain them to preserve history."""
