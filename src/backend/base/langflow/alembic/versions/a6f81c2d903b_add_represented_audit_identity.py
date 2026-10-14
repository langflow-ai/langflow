"""Add represented audit identity without removing the deprecated acting columns.

Revision ID: a6f81c2d903b
Revises: e5a7c9b1d3f2
Create Date: 2026-10-14

Phase: EXPAND

Keep old columns, constraints and indexes for rolling upgrades. Backfill existing
identity pairs in bounded batches. New writers populate both pairs; readers
fall back to acting columns for rows inserted by old processes after backfill.
Downgrade preserves the additive columns and all audit history. Removing the old
columns requires a later CONTRACT release after old writers have stopped.
"""

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision = "a6f81c2d903b"  # pragma: allowlist secret
down_revision = "e5a7c9b1d3f2"  # pragma: allowlist secret
branch_labels = None
depends_on = None

TABLE = "audit_events"
CHECK = "ck_audit_events_represented_pair"
INDEX = "ix_audit_events_represented_timeline"


def upgrade() -> None:
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
    indexes = {item["name"] for item in sa.inspect(conn).get_indexes(TABLE)}
    if INDEX not in indexes:
        op.create_index(INDEX, TABLE, ["represented_issuer", "represented_subject", "timestamp"])
    table = sa.Table(TABLE, sa.MetaData(), autoload_with=conn)
    pending = sa.and_(
        table.c.represented_issuer.is_(None),
        table.c.represented_subject.is_(None),
        table.c.acting_issuer.is_not(None),
        table.c.acting_subject.is_not(None),
    )
    while ids := list(conn.execute(sa.select(table.c.id).where(pending).limit(1000)).scalars()):
        conn.execute(
            sa.update(table)
            .where(table.c.id.in_(ids))
            .values(represented_issuer=table.c.acting_issuer, represented_subject=table.c.acting_subject)
        )


def downgrade() -> None:
    """Old binaries ignore the added columns; retain them to preserve history."""
