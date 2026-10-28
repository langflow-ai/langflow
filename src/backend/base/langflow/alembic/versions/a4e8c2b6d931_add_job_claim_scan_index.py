"""add_job_claim_scan_index

Revision ID: a4e8c2b6d931
Revises: 1d8d193028c8
Create Date: 2026-07-23 12:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "a4e8c2b6d931"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "1d8d193028c8"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "ix_job_claim_scan"
_COLUMNS = ["status", "type", "created_timestamp"]


def _present(conn) -> bool:
    return _INDEX in {index["name"] for index in sa.inspect(conn).get_indexes("job")}


def _is_invalid(conn) -> bool:
    """True when Postgres left the index INVALID after a failed concurrent build.

    A cancelled ``CREATE INDEX CONCURRENTLY`` leaves the index in place but unusable,
    and the inspector still reports it. Without this the retry would see it present
    and skip, leaving a dead index the planner never uses.
    """
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM pg_class c JOIN pg_index i ON i.indexrelid = c.oid "
                "WHERE i.indrelid = 'job'::regclass AND NOT i.indisvalid AND c.relname = :name"
            ),
            {"name": _INDEX},
        ).first()
        is not None
    )


def upgrade() -> None:
    """Composite index for the scaled backend's claim poll and watchdog scan.

    ``claim_next_queued_lease`` filters ``status`` + ``type`` and sorts by
    ``created_timestamp`` on every worker poll; the watchdog scans ``status`` +
    ``type`` on its interval. ``ix_job_status_created`` cannot serve either: the
    ``type`` filter sits between its two sorted columns.

    Built concurrently on Postgres. This migration runs for every deployment
    upgrading to 1.14, not only those that opt into the scaled backend, and ``job``
    holds a row for every flow run. A plain CREATE INDEX holds a write lock for the
    whole build, which stalls the old pod still serving traffic during a rolling
    deploy. CONCURRENTLY cannot run inside the migration transaction.
    """
    conn = op.get_bind()
    if not migration.table_exists("job", conn):
        return
    is_postgres = conn.dialect.name == "postgresql"
    present = _present(conn)

    if is_postgres and present and _is_invalid(conn):
        # Drop before rebuilding, otherwise the name is taken by a dead index.
        with op.get_context().autocommit_block():
            op.drop_index(_INDEX, table_name="job", postgresql_concurrently=True)
        present = False

    if present:
        return

    if is_postgres:
        with op.get_context().autocommit_block():
            op.create_index(_INDEX, "job", _COLUMNS, unique=False, postgresql_concurrently=True)
    else:
        op.create_index(_INDEX, "job", _COLUMNS, unique=False)


def downgrade() -> None:
    """Drop the claim-scan index, leaving job rows untouched."""
    conn = op.get_bind()
    if not migration.table_exists("job", conn):
        return
    if not _present(conn):
        return
    if conn.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.drop_index(_INDEX, table_name="job", postgresql_concurrently=True)
    else:
        op.drop_index(_INDEX, table_name="job")
