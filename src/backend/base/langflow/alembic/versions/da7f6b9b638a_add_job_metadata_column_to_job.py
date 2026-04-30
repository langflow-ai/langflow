"""Add job_metadata column to job

Revision ID: da7f6b9b638a
Revises: e728126476a8
Create Date: 2026-04-30 17:30:00.000000

Phase: EXPAND
Safe to rollback: YES (column is nullable; older services continue
    operating without ever reading the column).
Services compatible: All versions. New code writes per-domain progress
    / outcome data into ``job_metadata`` from inside
    ``execute_with_status``; old code simply ignores it. A CONTRACT
    migration to drop the legacy ``ingestion_run`` table can happen in
    a later phase once read-paths and the UI are migrated and a
    backfill has run.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "da7f6b9b638a"  # pragma: allowlist secret
down_revision: str | None = "e728126476a8"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "job"
COLUMN_NAME = "job_metadata"

# JSONB on Postgres for binary storage + GIN-indexable paths, JSON
# elsewhere. Matches the variant used on ``ingestion_run`` and
# ``knowledge_base`` JSON columns.
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
