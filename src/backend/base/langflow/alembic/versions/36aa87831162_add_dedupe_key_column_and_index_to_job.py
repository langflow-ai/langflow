"""add dedupe_key column and index to job table

Revision ID: 36aa87831162
Revises: a1b2c3d4e5f6
Create Date: 2026-03-31 00:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "36aa87831162"  # pragma: allowlist secret
down_revision: str | None = "a1b2c3d4e5f6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("job")}

    with op.batch_alter_table("job", schema=None) as batch_op:
        if not migration.column_exists("job", "dedupe_key", conn):
            batch_op.add_column(sa.Column("dedupe_key", sa.String(), nullable=True))
        if "ix_job_dedupe_key" not in existing_indexes:
            batch_op.create_index(batch_op.f("ix_job_dedupe_key"), ["dedupe_key"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_job_dedupe_key"))
        batch_op.drop_column("dedupe_key")
