"""add_job_claim_scan_index

Revision ID: a4e8c2b6d931
Revises: 1d8d193028c8
Create Date: 2026-07-23 12:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4e8c2b6d931"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "1d8d193028c8"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "ix_job_claim_scan"


def upgrade() -> None:
    """Composite index for the scaled backend's claim poll and watchdog scan.

    ``claim_next_queued_lease`` filters ``status`` + ``type`` and sorts by
    ``created_timestamp`` on every worker poll; the watchdog scans
    ``status`` + ``type`` on its interval. ``ix_job_status_created`` cannot serve
    either: the ``type`` filter sits between its two sorted columns. Without this
    index the hottest query in the fleet is a scan+sort over every row retention
    has not yet removed.
    """
    conn = op.get_bind()
    existing = {ix["name"] for ix in sa.inspect(conn).get_indexes("job")}
    if _INDEX not in existing:
        op.create_index(_INDEX, "job", ["status", "type", "created_timestamp"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    existing = {ix["name"] for ix in sa.inspect(conn).get_indexes("job")}
    if _INDEX in existing:
        op.drop_index(_INDEX, table_name="job")
