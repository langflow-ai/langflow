"""add_job_claim_scan_index

Revision ID: 4b8f2c6d9e1a
Revises: d19e7b3c5a42
Create Date: 2026-07-23 12:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4b8f2c6d9e1a"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "d19e7b3c5a42"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "ix_job_claim_scan"


def upgrade() -> None:
    """Composite index for the scaled backend's claim poll and watchdog scan.

    ``claim_next_queued_lease`` filters ``status`` + ``type`` and sorts by
    ``created_timestamp`` on every worker poll; the watchdog scans
    ``status`` + ``type`` on its interval. The job table has no retention, so
    without this index the hottest query is an ever-growing scan+sort.
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
