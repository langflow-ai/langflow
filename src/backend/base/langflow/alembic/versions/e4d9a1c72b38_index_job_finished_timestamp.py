"""Index job.finished_timestamp for the background metrics duration window.

The metrics collector ranges over ``finished_timestamp`` every tick to build the
run-duration percentiles. That column was unindexed, so the scan grew with the
whole job history rather than with the window being measured.

The collector's other queries filter ``status`` and ``type`` and take a MIN over
``created_timestamp``, which ``ix_job_claim_scan (status, type,
created_timestamp)`` already serves, so no second composite index is added here.

Additive only. Creating an index carries no data with it, and the down path
drops it again.

Revision ID: e4d9a1c72b38
Revises: c3b8d5f2a760
Create Date: 2026-09-23

Phase: EXPAND
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "e4d9a1c72b38"  # pragma: allowlist secret
down_revision: str | None = "c3b8d5f2a760"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existing_indexes(conn) -> set[str]:
    inspector = sa.inspect(conn)
    if "job" not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes("job")}


def upgrade() -> None:
    conn = op.get_bind()
    if "ix_job_finished_timestamp" not in _existing_indexes(conn):
        op.create_index("ix_job_finished_timestamp", "job", ["finished_timestamp"])


def downgrade() -> None:
    conn = op.get_bind()
    if "ix_job_finished_timestamp" in _existing_indexes(conn):
        op.drop_index("ix_job_finished_timestamp", table_name="job")
