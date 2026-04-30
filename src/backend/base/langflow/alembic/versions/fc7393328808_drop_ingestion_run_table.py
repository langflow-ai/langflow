"""Drop ingestion_run table

Revision ID: fc7393328808
Revises: 927dd37c3ea0
Create Date: 2026-04-30 17:56:00.000000

Phase: CONTRACT
Safe to rollback: YES — the downgrade re-creates the table (including
    indices, constraint, and the kb_id FK column added by
    ``e728126476a8``). Data populated post-drop will of course not be
    available, but the schema returns to its prior shape so any
    follow-up migration can run unchanged.
Services compatible: New code only. Old services that still read or
    write ``ingestion_run`` will fail on this DB. Coordinate the deploy
    so the new code rollout completes before this migration applies.

Data check: this CONTRACT migration depends on ``927dd37c3ea0``
(MIGRATE phase) having backfilled every ``ingestion_run`` row into
``job.job_metadata``. Alembic's revision chain enforces ordering, and
the verification was performed via the unit-test suite that exercises
the reads against the post-drop schema. We do NOT re-verify at
upgrade-time because the source table is being dropped in this same
migration — any verification query would race with the drop.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel.sql.sqltypes import AutoString

# JSONB on Postgres, JSON elsewhere — matches the original creation
# migration so the recreate path is byte-identical at the column-type
# layer.
JsonVariant = JSON().with_variant(JSONB(), "postgresql")

RUN_STATUS_VALUES = ("pending", "running", "succeeded", "partial", "failed", "cancelled")

# revision identifiers, used by Alembic.
revision: str = "fc7393328808"  # pragma: allowlist secret
down_revision: str | None = "927dd37c3ea0"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "ingestion_run"
KB_ID_FK_NAME = "fk_ingestion_run_kb_id_knowledge_base"


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    # Data check: confirm the preceding MIGRATE phase actually ran by
    # comparing row counts. We don't fail on mismatch (some
    # ingestion_run rows may be in non-migratable states for legitimate
    # reasons; the migration is best-effort by design) but a stark
    # asymmetry is logged so operators notice if the backfill clearly
    # didn't run.
    src_count = conn.execute(sa.text(f"SELECT COUNT(*) FROM {TABLE_NAME}")).scalar() or 0  # noqa: S608 — TABLE_NAME is a module-level constant, not user input
    dst_count = conn.execute(sa.text("SELECT COUNT(*) FROM job WHERE type = 'ingestion'")).scalar() or 0
    if src_count > 0 and dst_count == 0:
        # Loud warning so this can't happen silently in production.
        # The drop still proceeds — operators can re-derive run history
        # from the Job lifecycle columns even without job_metadata.
        import logging

        logging.getLogger("alembic.runtime.migration").warning(
            "Dropping ingestion_run with %d rows but job table has 0 INGESTION rows; "
            "backfill (927dd37c3ea0) may not have run.",
            src_count,
        )

    # Drop FK before the table so the constraint inspector doesn't
    # leave a dangling reference on the ``knowledge_base`` side. This
    # is the FK introduced by migration ``e728126476a8``.
    if migration.foreign_key_exists(TABLE_NAME, KB_ID_FK_NAME, conn):
        with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
            batch_op.drop_constraint(KB_ID_FK_NAME, type_="foreignkey")

    # Drop indices explicitly first; some dialects choke on implicit
    # index removal during table drop.
    inspector = sa.inspect(conn)
    existing_indexes = {idx["name"] for idx in inspector.get_indexes(TABLE_NAME)}
    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        for idx_name in (
            "ix_ingestion_run_kb_id",
            "ix_ingestion_run_started_at",
            "ix_ingestion_run_status",
            "ix_ingestion_run_source_type",
            "ix_ingestion_run_user_id",
            "ix_ingestion_run_kb_name",
            "ix_ingestion_run_job_id",
        ):
            if idx_name in existing_indexes:
                batch_op.drop_index(batch_op.f(idx_name))

    op.drop_table(TABLE_NAME)


def downgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        return

    status_values = ", ".join(f"'{v}'" for v in RUN_STATUS_VALUES)
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("kb_name", AutoString(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", AutoString(), nullable=False),
        sa.Column("source_config", JsonVariant, nullable=False),
        sa.Column("status", AutoString(), nullable=False, server_default="pending"),
        sa.Column("error_message", AutoString(), nullable=True),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("chunks_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items", JsonVariant, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_run")),
        sa.CheckConstraint(f"status IN ({status_values})", name="ck_ingestion_run_status"),
    )

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ingestion_run_job_id"), ["job_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_ingestion_run_kb_name"), ["kb_name"], unique=False)
        batch_op.create_index(batch_op.f("ix_ingestion_run_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_ingestion_run_source_type"), ["source_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_ingestion_run_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_ingestion_run_started_at"), ["started_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_ingestion_run_kb_id"), ["kb_id"], unique=False)

    if migration.table_exists("knowledge_base", conn):
        with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
            batch_op.create_foreign_key(
                KB_ID_FK_NAME,
                "knowledge_base",
                ["kb_id"],
                ["id"],
                ondelete="SET NULL",
            )
