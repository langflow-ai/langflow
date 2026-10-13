"""Preserve background-job metric totals after retention deletes job history.

The retention transaction adds purged outcomes to this fixed-size rollup before
deleting the jobs. The collector combines it with retained jobs in one snapshot.
The singleton row is created lazily, so this migration does not seed or backfill
data and cannot recover jobs deleted before it was installed.

Revision ID: b8e1f3a5c709
Revises: d6f8a0c2e4b9
Create Date: 2026-10-01

Phase: EXPAND
Warning: downgrade permanently discards archived metric totals. Retained job
rows are preserved, but upgrading again cannot restore the discarded totals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b8e1f3a5c709"  # pragma: allowlist secret
down_revision: str | None = "d6f8a0c2e4b9"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if not migration.table_exists("background_job_metric_totals", conn):
        op.create_table(
            "background_job_metric_totals",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("started", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
            sa.Column("completed", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
            sa.Column("failed_error", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
            sa.Column("failed_worker_lost", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
            sa.Column("failed_input_timeout", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
            sa.Column("timed_out", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
            sa.Column("cancelled", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    """Drop the rollup, permanently losing totals for already-purged jobs."""
    from langflow.utils import migration

    conn = op.get_bind()
    if migration.table_exists("background_job_metric_totals", conn):
        op.drop_table("background_job_metric_totals")
