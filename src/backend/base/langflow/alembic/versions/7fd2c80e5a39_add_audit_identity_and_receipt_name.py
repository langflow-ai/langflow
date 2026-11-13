"""Add represented audit identity and retain names on pruned replacement receipts.

Revision ID: 7fd2c80e5a39
Revises: 310c015b3c92
Phase: EXPAND

Keep existing acting identity and audit history. Bound both identity indexes.
Retain the added columns during downgrade so older binaries can ignore them.
"""

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision = "7fd2c80e5a39"  # pragma: allowlist secret
down_revision = "310c015b3c92"  # pragma: allowlist secret
branch_labels = None
depends_on = None

TABLE = "audit_events"
CHECK = "ck_audit_events_represented_pair"
CHECK_EXPRESSION = (
    "(represented_issuer IS NULL AND represented_subject IS NULL) "
    "OR (represented_issuer IS NOT NULL AND represented_subject IS NOT NULL)"
)
RECEIPTS = "project_replacement_operation"
# Bound the B-tree keys. The issuer remains in the table for exact filtering.
INDEXES = {
    "ix_audit_events_acting_timeline": ["acting_subject", "timestamp"],
    "ix_audit_events_represented_timeline": ["represented_subject", "timestamp"],
}


def _postgres_upgrade(
    conn: sa.Connection, missing: list[sa.Column], indexes: dict[str, list[str]], *, add_check: bool
) -> None:
    for column in missing:
        op.add_column(TABLE, column)
    if add_check:
        op.create_check_constraint(op.f(CHECK), TABLE, CHECK_EXPRESSION, postgresql_not_valid=True)

    # A cancelled concurrent build can leave an index present but unusable.
    invalid = set(
        conn.scalars(
            sa.text(
                "SELECT c.relname FROM pg_class c JOIN pg_index i ON i.indexrelid = c.oid "
                "WHERE i.indrelid = 'audit_events'::regclass AND NOT i.indisvalid AND c.relname = ANY(:names)"
            ),
            {"names": list(INDEXES)},
        )
    )
    # Commit the short exclusive lock before scanning existing rows. Validation
    # and concurrent index builds allow the other replicas to keep writing.
    with op.get_context().autocommit_block():
        op.execute(f"ALTER TABLE {TABLE} VALIDATE CONSTRAINT {CHECK}")
        for name, columns in INDEXES.items():
            if indexes.get(name) == columns and name not in invalid:
                continue
            if name in indexes:
                op.drop_index(name, table_name=TABLE, postgresql_concurrently=True)
            op.create_index(name, TABLE, columns, postgresql_concurrently=True)


def upgrade() -> None:
    """Add the migration changes without rewriting existing audit history."""
    conn = op.get_bind()
    if migration.table_exists(RECEIPTS, conn) and not migration.column_exists(RECEIPTS, "project_name", conn):
        op.add_column(RECEIPTS, sa.Column("project_name", sa.String(), nullable=True))

    if not migration.table_exists(TABLE, conn):
        return
    inspector = sa.inspect(conn)
    existing_columns = {column["name"] for column in inspector.get_columns(TABLE)}
    missing = [
        sa.Column(name, sa.String(length), nullable=True)
        for name, length in (("represented_issuer", 2048), ("represented_subject", 512))
        if name not in existing_columns
    ]
    add_check = CHECK not in {item["name"] for item in inspector.get_check_constraints(TABLE)}
    indexes = {item["name"]: item["column_names"] for item in inspector.get_indexes(TABLE)}
    if conn.dialect.name == "postgresql":
        _postgres_upgrade(conn, missing, indexes, add_check=add_check)
        return

    rebuild_indexes = {name: columns for name, columns in INDEXES.items() if indexes.get(name) != columns}
    # Drop old definitions before the SQLite batch reflects and recreates indexes.
    for name in rebuild_indexes:
        if name in indexes:
            op.drop_index(name, table_name=TABLE)
    if missing or add_check:
        with op.batch_alter_table(TABLE) as batch:
            for column in missing:
                batch.add_column(column)
            if add_check:
                batch.create_check_constraint(op.f(CHECK), CHECK_EXPRESSION)
    for name, columns in rebuild_indexes.items():
        op.create_index(name, TABLE, columns)


def downgrade() -> None:
    """Keep the audit history and receipt names for subsequent upgrades."""
