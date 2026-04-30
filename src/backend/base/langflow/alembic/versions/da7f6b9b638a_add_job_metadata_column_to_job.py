"""Add job_metadata column to job

Revision ID: da7f6b9b638a
Revises: 15fe9304bca7
Create Date: 2026-04-30 17:30:00.000000

Phase: EXPAND
Safe to rollback: YES (column is nullable; older services continue
    operating without ever reading the column).
Services compatible: All versions. New code writes per-domain progress
    / outcome data into ``job_metadata`` from inside
    ``execute_with_status``; old code simply ignores it.

Originally part of an expand-contract sequence that also created a
parallel ``ingestion_run`` table and later dropped it. The full
sequence collapsed to this single migration once it was clear the
``ingestion_run`` table never shipped to any tagged release —
production users only ever experience the unified ``Job.job_metadata``
surface.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "da7f6b9b638a"  # pragma: allowlist secret
down_revision: str | None = "15fe9304bca7"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "job"
COLUMN_NAME = "job_metadata"

# JSONB on Postgres for binary storage + GIN-indexable paths, JSON
# elsewhere. Matches the variant used on the ``knowledge_base`` JSON
# columns and on the matching SQLModel so ORM and DDL agree.
JsonVariant = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    if not migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        op.add_column(TABLE_NAME, sa.Column(COLUMN_NAME, JsonVariant, nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    if migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
            batch_op.drop_column(COLUMN_NAME)
