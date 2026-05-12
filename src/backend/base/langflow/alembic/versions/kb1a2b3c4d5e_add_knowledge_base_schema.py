"""Add knowledge_base + ingestion_run schema and job.job_metadata.

Revision ID: kb1a2b3c4d5e
Revises: b4c2f8e9a1d3
Create Date: 2026-05-01 08:30:00.000000

Phase: EXPAND
Safe to rollback: YES (all new tables and a single nullable column).
Services compatible: All versions — older services either ignore the
    new tables entirely or fall back to JSON-on-disk for KB metadata;
    newer services prefer the DB.

Consolidates the KB / ingestion-run / job-metadata work from the
``feat/kb-v1-db-connectors`` branch into a single migration. Replaces
the original chain of six (knowledge_base, ingestion_run,
ingestion_run.kb_id, ingestion_run.user_metadata, job.job_metadata,
plus a merge head) before any tagged release shipped — the schema is
identical to the prior chain at HEAD, so any existing dev databases
that already ran the old chain should ``alembic stamp head`` to this
revision rather than re-running.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel.sql.sqltypes import AutoString

# JSONB on Postgres (binary, dedup, GIN-indexable), JSON elsewhere.
# Same variant used on the matching SQLModels so ORM/DDL agree.
JsonVariant = JSON().with_variant(JSONB(), "postgresql")

# Allow-list for ``knowledge_base.status``. Keep in sync with
# ``KnowledgeBaseStatus`` (services/database/models/knowledge_base/model.py).
KB_STATUS_VALUES = ("creating", "ready", "ingesting", "failed")

# Allow-list for ``ingestion_run.status``. Keep in sync with
# ``IngestionRunStatus`` Python enum.
RUN_STATUS_VALUES = ("pending", "running", "succeeded", "partial", "failed", "cancelled")

# revision identifiers, used by Alembic.
revision: str = "kb1a2b3c4d5e"  # pragma: allowlist secret
down_revision: str | None = "b4c2f8e9a1d3"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KB_TABLE = "knowledge_base"
KB_UNIQUE = "uq_knowledge_base_user_name"
RUN_TABLE = "ingestion_run"
RUN_FK_NAME = "fk_ingestion_run_kb_id_knowledge_base"
JOB_TABLE = "job"
JOB_METADATA_COLUMN = "job_metadata"


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------ #
    #  knowledge_base                                                    #
    # ------------------------------------------------------------------ #
    if not migration.table_exists(KB_TABLE, conn):
        kb_status_values = ", ".join(f"'{v}'" for v in KB_STATUS_VALUES)
        op.create_table(
            KB_TABLE,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", AutoString(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            # ``model_selection`` is the single source of truth for
            # embedding config; the legacy flat columns
            # (``embedding_provider`` / ``embedding_model``) were never
            # shipped — derived views over ``model_selection`` are
            # exposed via helpers instead.
            sa.Column("model_selection", JsonVariant, nullable=False),
            sa.Column("chunk_size", sa.Integer(), nullable=False, server_default="1000"),
            sa.Column("chunk_overlap", sa.Integer(), nullable=False, server_default="200"),
            sa.Column("separator", AutoString(), nullable=True),
            sa.Column("column_config", JsonVariant, nullable=False),
            sa.Column("backend_type", AutoString(), nullable=False, server_default="chroma"),
            sa.Column("backend_config", JsonVariant, nullable=False),
            sa.Column("chunks", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("words", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("characters", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("source_types", JsonVariant, nullable=False),
            sa.Column("status", AutoString(), nullable=False, server_default="ready"),
            sa.Column("failure_reason", AutoString(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_base")),
            sa.UniqueConstraint("user_id", "name", name=KB_UNIQUE),
            # Referential integrity: a deleted user takes their KBs with
            # them. Application-level scoping already filters by user_id,
            # but DB-enforced CASCADE prevents orphans from surviving a
            # raw ``DELETE FROM user``.
            sa.ForeignKeyConstraint(
                ["user_id"], ["user.id"], name="fk_knowledge_base_user_id_user", ondelete="CASCADE"
            ),
            # Value allow-list mirrors the ``KnowledgeBaseStatus`` Python
            # enum. A typo in app code now fails at COMMIT instead of
            # silently storing an invalid state.
            sa.CheckConstraint(f"status IN ({kb_status_values})", name="ck_knowledge_base_status"),
        )

        with op.batch_alter_table(KB_TABLE, schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_knowledge_base_name"), ["name"], unique=False)
            batch_op.create_index(batch_op.f("ix_knowledge_base_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_knowledge_base_status"), ["status"], unique=False)

    # ------------------------------------------------------------------ #
    #  ingestion_run (table + kb_id FK + user_metadata in one shot)      #
    # ------------------------------------------------------------------ #
    if not migration.table_exists(RUN_TABLE, conn):
        run_status_values = ", ".join(f"'{v}'" for v in RUN_STATUS_VALUES)
        op.create_table(
            RUN_TABLE,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("job_id", sa.Uuid(), nullable=True),
            sa.Column("kb_name", AutoString(), nullable=False),
            # ``kb_id`` is nullable so older runs (pre-FK rollout) and
            # runs whose KB has been deleted (``ON DELETE SET NULL``)
            # remain readable. The string ``kb_name`` column stays for
            # N-1 compatibility; both columns are written by new code.
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
            # BigInteger: a run ingesting large cloud-storage blobs can
            # exceed the 2 GB int32 ceiling. ``knowledge_base.size_bytes``
            # uses BigInteger for the same reason.
            sa.Column("total_bytes", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("chunks_created", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("items", JsonVariant, nullable=False),
            # Empty objects (``{}``) are written when no user metadata
            # is supplied so list endpoints can treat presence/absence
            # of tags consistently.
            sa.Column("user_metadata", JsonVariant, nullable=False, server_default="{}"),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_run")),
            # ``ON DELETE SET NULL`` keeps run history readable after a
            # KB is deleted (runs show "deleted KB" rather than
            # disappearing) while guaranteeing no dangling ``kb_id``.
            sa.ForeignKeyConstraint(["kb_id"], [f"{KB_TABLE}.id"], name=RUN_FK_NAME, ondelete="SET NULL"),
            # Value allow-list mirrors ``IngestionRunStatus``. Prevents
            # typos ("Running" vs "running") from silently storing an
            # invalid state that list filters can't match.
            sa.CheckConstraint(f"status IN ({run_status_values})", name="ck_ingestion_run_status"),
        )

        with op.batch_alter_table(RUN_TABLE, schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_ingestion_run_job_id"), ["job_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_ingestion_run_kb_name"), ["kb_name"], unique=False)
            batch_op.create_index(batch_op.f("ix_ingestion_run_kb_id"), ["kb_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_ingestion_run_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_ingestion_run_source_type"), ["source_type"], unique=False)
            batch_op.create_index(batch_op.f("ix_ingestion_run_status"), ["status"], unique=False)
            # List endpoints sort by started_at DESC — without this
            # index, a KB with hundreds of thousands of runs sequential-scans.
            batch_op.create_index(batch_op.f("ix_ingestion_run_started_at"), ["started_at"], unique=False)

    # ------------------------------------------------------------------ #
    #  job.job_metadata                                                  #
    # ------------------------------------------------------------------ #
    if migration.table_exists(JOB_TABLE, conn) and not migration.column_exists(JOB_TABLE, JOB_METADATA_COLUMN, conn):
        # Per-domain progress / outcome data written from inside
        # ``execute_with_status``. Old code simply ignores it.
        op.add_column(JOB_TABLE, sa.Column(JOB_METADATA_COLUMN, JsonVariant, nullable=True))


def downgrade() -> None:
    conn = op.get_bind()

    # job.job_metadata --------------------------------------------------- #
    if migration.table_exists(JOB_TABLE, conn) and migration.column_exists(JOB_TABLE, JOB_METADATA_COLUMN, conn):
        with op.batch_alter_table(JOB_TABLE, schema=None) as batch_op:
            batch_op.drop_column(JOB_METADATA_COLUMN)

    # ingestion_run ------------------------------------------------------ #
    if migration.table_exists(RUN_TABLE, conn):
        with op.batch_alter_table(RUN_TABLE, schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_ingestion_run_started_at"))
            batch_op.drop_index(batch_op.f("ix_ingestion_run_status"))
            batch_op.drop_index(batch_op.f("ix_ingestion_run_source_type"))
            batch_op.drop_index(batch_op.f("ix_ingestion_run_user_id"))
            batch_op.drop_index(batch_op.f("ix_ingestion_run_kb_id"))
            batch_op.drop_index(batch_op.f("ix_ingestion_run_kb_name"))
            batch_op.drop_index(batch_op.f("ix_ingestion_run_job_id"))
        op.drop_table(RUN_TABLE)

    # knowledge_base ----------------------------------------------------- #
    if migration.table_exists(KB_TABLE, conn):
        with op.batch_alter_table(KB_TABLE, schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_knowledge_base_status"))
            batch_op.drop_index(batch_op.f("ix_knowledge_base_user_id"))
            batch_op.drop_index(batch_op.f("ix_knowledge_base_name"))
        op.drop_table(KB_TABLE)
