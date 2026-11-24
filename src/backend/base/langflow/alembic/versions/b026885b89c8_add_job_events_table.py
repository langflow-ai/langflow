"""add job_events table for durable background-job event log.

Revision ID: b026885b89c8
Revises: 185482a2d715
Create Date: 2026-06-03 10:05:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b026885b89c8"  # pragma: allowlist secret
down_revision: str | None = "185482a2d715"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if not migration.table_exists("job_events", conn):
        op.create_table(
            "job_events",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("job_id", sa.Uuid(), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("payload", _JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("job_id", "seq", name="uq_job_events_job_id_seq"),
        )
        with op.batch_alter_table("job_events", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_job_events_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_job_events_job_id"), ["job_id"], unique=False)


def downgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if migration.table_exists("job_events", conn):
        op.drop_table("job_events")
