"""Add represented audit identity and retain names on pruned replacement receipts.

Revision ID: 7fd2c80e5a39
Revises: f6a2c8e4b901
Phase: EXPAND

Keep existing acting identity and audit history. Bound both identity indexes.
Retain the added columns during downgrade so older binaries can ignore them.
"""

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision = "7fd2c80e5a39"  # pragma: allowlist secret
down_revision = "f6a2c8e4b901"  # pragma: allowlist secret
branch_labels = None
depends_on = None

TABLE = "audit_events"
CHECK = "ck_audit_events_represented_pair"
RECEIPTS = "project_replacement_operation"


def upgrade() -> None:
    """Add the migration changes without rewriting existing audit history."""
    conn = op.get_bind()
    if migration.table_exists(RECEIPTS, conn) and not migration.column_exists(RECEIPTS, "project_name", conn):
        op.add_column(RECEIPTS, sa.Column("project_name", sa.String(), nullable=True))

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
    """Keep the audit history and receipt names for subsequent upgrades."""
