"""Index job status and timestamps for the background metrics collector.

The collector runs every tick against a table with no retention, filtering on ``status`` and
taking a MIN over ``created_timestamp`` for queued jobs and a range over
``finished_timestamp`` for the duration window. None of those columns were indexed, and
``status`` was explicitly ``index=False``, so each tick's cost grew with the whole job
history rather than with the work in flight.

Additive only. Creating an index carries no data with it, and the down path drops it again.

Revision ID: b3f7c2a91d48
Revises: a3f8b1c9d7e2
Create Date: 2026-08-25

Phase: EXPAND
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b3f7c2a91d48"  # pragma: allowlist secret
down_revision: str | None = "a3f8b1c9d7e2"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existing_indexes(conn) -> set[str]:
    inspector = sa.inspect(conn)
    if "job" not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes("job")}


def upgrade() -> None:
    conn = op.get_bind()
    existing = _existing_indexes(conn)
    # Composite rather than an index on status alone: the same index serves both the
    # per-status counts and the MIN over created_timestamp for the oldest queued job.
    if "ix_job_status_created" not in existing:
        op.create_index("ix_job_status_created", "job", ["status", "created_timestamp"])
    if "ix_job_finished_timestamp" not in existing:
        op.create_index("ix_job_finished_timestamp", "job", ["finished_timestamp"])


def downgrade() -> None:
    conn = op.get_bind()
    existing = _existing_indexes(conn)
    if "ix_job_finished_timestamp" in existing:
        op.drop_index("ix_job_finished_timestamp", table_name="job")
    if "ix_job_status_created" in existing:
        op.drop_index("ix_job_status_created", table_name="job")
