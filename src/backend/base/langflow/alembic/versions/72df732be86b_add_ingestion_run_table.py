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
from sqlmodel.sql.sqltypes import AutoString

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

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("kb_name", AutoString(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", AutoString(), nullable=False),
        sa.Column("source_config", sa.JSON(), nullable=False),
        sa.Column("status", AutoString(), nullable=False, server_default="pending"),
        sa.Column("error_message", AutoString(), nullable=True),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunks_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_run")),
    )

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ingestion_run_job_id"), ["job_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_ingestion_run_kb_name"), ["kb_name"], unique=False)
        batch_op.create_index(batch_op.f("ix_ingestion_run_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_ingestion_run_source_type"), ["source_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_ingestion_run_status"), ["status"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ingestion_run_status"))
        batch_op.drop_index(batch_op.f("ix_ingestion_run_source_type"))
        batch_op.drop_index(batch_op.f("ix_ingestion_run_user_id"))
        batch_op.drop_index(batch_op.f("ix_ingestion_run_kb_name"))
        batch_op.drop_index(batch_op.f("ix_ingestion_run_job_id"))

    op.drop_table(TABLE_NAME)
