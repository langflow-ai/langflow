"""add job.lease_heartbeat_at for the scaled claim poll.

Typed mirror of job_metadata["heartbeat_at"], so the worker claim poll can
exclude QUEUED rows whose lease is still fresh in its WHERE clause instead of
discovering it one row at a time after the candidate window is already full.

Nullable with no backfill: a NULL lease reads as claimable, which is what every
existing row should be, and the column fills itself as leases are taken.

Revision ID: e3b7d1c4a95f
Revises: a4e8c2b6d931
Create Date: 2026-10-28 10:14:22.108734

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3b7d1c4a95f"  # pragma: allowlist secret
down_revision: str | None = "a4e8c2b6d931"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "job"
_COLUMN = "lease_heartbeat_at"


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(_TABLE):
        return
    # A fresh database has already created the column from the model.
    if _COLUMN in {col["name"] for col in inspector.get_columns(_TABLE)}:
        return
    with op.batch_alter_table(_TABLE, schema=None) as batch_op:
        batch_op.add_column(sa.Column(_COLUMN, sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(_TABLE):
        return
    if _COLUMN not in {col["name"] for col in inspector.get_columns(_TABLE)}:
        return
    with op.batch_alter_table(_TABLE, schema=None) as batch_op:
        batch_op.drop_column(_COLUMN)
