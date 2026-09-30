"""add job_checkpoints table for durable suspend/resume checkpoints.

Stores one opaque, already-serialized checkpoint blob per (job_id, kind): the
graph producer writes JSON, the agent saver (LE-1447) writes base64(msgpack).
UNIQUE(job_id, kind) keeps a single live checkpoint per kind.

Revision ID: a1f4c9d27b30
Revises: c7412b389256
Create Date: 2026-06-15 09:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1f4c9d27b30"  # pragma: allowlist secret
down_revision: str | None = "c7412b389256"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if not migration.table_exists("job_checkpoints", conn):
        op.create_table(
            "job_checkpoints",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("job_id", sa.Uuid(), nullable=False),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("blob", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("job_id", "kind", name="uq_job_checkpoints_job_id_kind"),
        )
        with op.batch_alter_table("job_checkpoints", schema=None) as batch_op:
            # No index on ``id``: the PRIMARY KEY already provides a unique index, so a separate
            # ix_job_checkpoints_id would be dead duplicate DDL.
            batch_op.create_index(batch_op.f("ix_job_checkpoints_job_id"), ["job_id"], unique=False)


def downgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if migration.table_exists("job_checkpoints", conn):
        op.drop_table("job_checkpoints")
