"""Add ingestion_run table

Revision ID: 72df732be86b
Revises: d306e5c17c41
Create Date: 2026-04-20 13:15:00.000000

Phase: EXPAND
Safe to rollback: YES (table is new; no existing data depends on it)
Services compatible: All versions (older services simply don't write to
    the new table; newer services populate it on every
    ``perform_ingestion`` invocation).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel.sql.sqltypes import AutoString

# JSONB on Postgres, JSON elsewhere — same variant used on the
# matching SQLModel so ORM/DDL stay in sync.
JsonVariant = JSON().with_variant(JSONB(), "postgresql")

# Allow-list for ``ingestion_run.status``. Keep in sync with the
# ``IngestionRunStatus`` Python enum.
RUN_STATUS_VALUES = ("pending", "running", "succeeded", "partial", "failed", "cancelled")

# revision identifiers, used by Alembic.
revision: str = "72df732be86b"  # pragma: allowlist secret
down_revision: str | None = "d306e5c17c41"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "ingestion_run"


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        return

    status_values = ", ".join(f"'{v}'" for v in RUN_STATUS_VALUES)
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("kb_name", AutoString(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", AutoString(), nullable=False),
        sa.Column("source_config", JsonVariant, nullable=False),
        sa.Column("status", AutoString(), nullable=False, server_default="pending"),
        sa.Column("error_message", AutoString(), nullable=True),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        # BigInteger: a run ingesting large cloud-storage blobs can
        # exceed the 2 GB int32 ceiling. ``knowledge_base.size_bytes``
        # uses BigInteger for the same reason.
        sa.Column("total_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("chunks_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items", JsonVariant, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_run")),
        # Value allow-list mirrors ``IngestionRunStatus``. Prevents
        # typos ("Running" vs "running") from silently storing an
        # invalid state that list filters can't match.
        sa.CheckConstraint(f"status IN ({status_values})", name="ck_ingestion_run_status"),
    )

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ingestion_run_job_id"), ["job_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_ingestion_run_kb_name"), ["kb_name"], unique=False)
        batch_op.create_index(batch_op.f("ix_ingestion_run_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_ingestion_run_source_type"), ["source_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_ingestion_run_status"), ["status"], unique=False)
        # List endpoints sort by started_at DESC — without this index,
        # a KB with hundreds of thousands of runs sequential-scans.
        batch_op.create_index(batch_op.f("ix_ingestion_run_started_at"), ["started_at"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ingestion_run_started_at"))
        batch_op.drop_index(batch_op.f("ix_ingestion_run_status"))
        batch_op.drop_index(batch_op.f("ix_ingestion_run_source_type"))
        batch_op.drop_index(batch_op.f("ix_ingestion_run_user_id"))
        batch_op.drop_index(batch_op.f("ix_ingestion_run_kb_name"))
        batch_op.drop_index(batch_op.f("ix_ingestion_run_job_id"))

    op.drop_table(TABLE_NAME)
