"""make api_key expires_at timezone aware

Phase: EXPAND
Revision ID: c35e9db03a66
Revises: 7c8d9e0f1a2b
Create Date: 2026-05-27 15:42:07.976453

The expires_at column was originally added as DateTime (naive). Every writer in
the codebase passed UTC values, but Postgres dropped the tzinfo on write, so
reads came back naive and broke comparisons against timezone-aware now().

Backfill caveat: we cannot recover the original tzinfo. We interpret existing
values as UTC, which matches all known writers. On SQLite the column has no
distinct affinity, so this migration is a no-op there.

EXPAND rationale: this is a non-destructive type widening (TIMESTAMP →
TIMESTAMPTZ) executed via raw SQL. Existing rows are reinterpreted as UTC
without data loss; readers that ignore tzinfo continue to work. No follow-up
CONTRACT migration is required because we do not introduce a parallel column.
"""

from collections.abc import Sequence

from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "c35e9db03a66"  # pragma: allowlist secret
down_revision: str | None = "7c8d9e0f1a2b"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "apikey"
COLUMN_NAME = "expires_at"


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if not migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        return
    if conn.dialect.name != "postgresql":
        return
    op.execute(
        f"ALTER TABLE {TABLE_NAME} "
        f"ALTER COLUMN {COLUMN_NAME} TYPE TIMESTAMP WITH TIME ZONE "
        f"USING {COLUMN_NAME} AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if not migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        return
    if conn.dialect.name != "postgresql":
        return
    op.execute(
        f"ALTER TABLE {TABLE_NAME} "
        f"ALTER COLUMN {COLUMN_NAME} TYPE TIMESTAMP WITHOUT TIME ZONE "
        f"USING {COLUMN_NAME} AT TIME ZONE 'UTC'"
    )
