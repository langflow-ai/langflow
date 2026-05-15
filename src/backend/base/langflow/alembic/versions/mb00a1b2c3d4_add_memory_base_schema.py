"""add_memory_base_schema

Consolidates all Memory Base schema changes into a single migration:
  - job.dedupe_key (nullable String) + ix_job_dedupe_key
  - message.run_id (nullable UUID) + ix_message_run_id
  - message.is_output (bool, default false)
  - memory_base table + ix_memory_base_flow_id + ix_memory_base_user_id
  - memory_base_session table + three indexes
  - message_ingestion_record table + three indexes
  - memory_base_workflow_run table + two indexes

Phase: EXPAND

Revision ID: mb00a1b2c3d4
Revises: d306e5c17c41
Create Date: 2026-04-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "mb00a1b2c3d4"  # pragma: allowlist secret
down_revision: str | None = "d306e5c17c41"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------ #
    #  job.dedupe_key                                                     #
    # ------------------------------------------------------------------ #
    inspector = sa.inspect(conn)
    existing_job_indexes = {idx["name"] for idx in inspector.get_indexes("job")}
    with op.batch_alter_table("job", schema=None) as batch_op:
        if not migration.column_exists("job", "dedupe_key", conn):
            batch_op.add_column(sa.Column("dedupe_key", sa.String(), nullable=True))
        if "ix_job_dedupe_key" not in existing_job_indexes:
            batch_op.create_index(batch_op.f("ix_job_dedupe_key"), ["dedupe_key"], unique=False)

    # ------------------------------------------------------------------ #
    #  message.run_id + message.is_output                                 #
    # ------------------------------------------------------------------ #
    with op.batch_alter_table("message", schema=None) as batch_op:
        if not migration.column_exists("message", "run_id", conn):
            batch_op.add_column(sa.Column("run_id", sa.Uuid(), nullable=True))
        if not migration.column_exists("message", "is_output", conn):
            batch_op.add_column(sa.Column("is_output", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    existing_message_indexes = {idx["name"] for idx in sa.inspect(conn).get_indexes("message")}
    if "ix_message_run_id" not in existing_message_indexes:
        op.create_index("ix_message_run_id", "message", ["run_id"])

    # ------------------------------------------------------------------ #
    #  memory_base                                                         #
    # ------------------------------------------------------------------ #
    if not migration.table_exists("memory_base", conn):
        op.create_table(
            "memory_base",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("flow_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("threshold", sa.Integer(), nullable=False, server_default=sa.text("50")),
            sa.Column("auto_capture", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("embedding_model", sa.String(), nullable=False, server_default=sa.text("''")),
            sa.Column("preprocessing", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("preproc_model", sa.String(), nullable=True),
            sa.Column("preproc_instructions", sa.String(), nullable=True),
            sa.Column("kb_name", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "name", name="uq_memory_base_user_name"),
            sa.Index("ix_memory_base_flow_id", "flow_id"),
            sa.Index("ix_memory_base_user_id", "user_id"),
        )

    # ------------------------------------------------------------------ #
    #  memory_base_session                                                 #
    # ------------------------------------------------------------------ #
    if not migration.table_exists("memory_base_session", conn):
        op.create_table(
            "memory_base_session",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column(
                "memory_base_id",
                sa.Uuid(),
                sa.ForeignKey("memory_base.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("session_id", sa.String(), nullable=False),
            sa.Column("cursor_id", sa.Uuid(), nullable=True),
            sa.Column("total_processed", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("memory_base_id", "session_id", name="uq_memory_base_session"),
        )
        op.create_index("ix_memory_base_session_memory_base_id", "memory_base_session", ["memory_base_id"])
        op.create_index("ix_memory_base_session_session_id", "memory_base_session", ["session_id"])
        op.create_index(
            "ix_memory_base_session_lookup",
            "memory_base_session",
            ["memory_base_id", "session_id"],
        )

    # ------------------------------------------------------------------ #
    #  message_ingestion_record                                            #
    # ------------------------------------------------------------------ #
    if not migration.table_exists("message_ingestion_record", conn):
        op.create_table(
            "message_ingestion_record",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column(
                "message_id",
                sa.Uuid(),
                sa.ForeignKey("message.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "memory_base_id",
                sa.Uuid(),
                sa.ForeignKey("memory_base.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "job_id",
                sa.Uuid(),
                sa.ForeignKey("job.job_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("session_id", sa.String(), nullable=False),
            sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "message_id",
                "session_id",
                "memory_base_id",
                name="uq_mir_message_session_mb",
            ),
        )
        op.create_index("ix_mir_message_id", "message_ingestion_record", ["message_id"])
        op.create_index("ix_mir_job_id", "message_ingestion_record", ["job_id"])
        op.create_index(
            "ix_mir_memory_base_session",
            "message_ingestion_record",
            ["memory_base_id", "session_id"],
        )

    # ------------------------------------------------------------------ #
    #  memory_base_workflow_run                                            #
    # ------------------------------------------------------------------ #
    if not migration.table_exists("memory_base_workflow_run", conn):
        op.create_table(
            "memory_base_workflow_run",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column(
                "memory_base_id",
                sa.Uuid(),
                sa.ForeignKey("memory_base.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("session_id", sa.String(), nullable=False),
            sa.Column(
                "workflow_job_id",
                sa.Uuid(),
                sa.ForeignKey("job.job_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "ingestion_job_id",
                sa.Uuid(),
                sa.ForeignKey("job.job_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "memory_base_id",
                "session_id",
                "workflow_job_id",
                name="uq_mbwr_mb_session_wf_job",
            ),
        )
        op.create_index("ix_mbwr_mb_session", "memory_base_workflow_run", ["memory_base_id", "session_id"])
        op.create_index("ix_mbwr_ingestion_job_id", "memory_base_workflow_run", ["ingestion_job_id"])


def downgrade() -> None:
    conn = op.get_bind()

    # Children first (FK dependencies) ----------------------------------- #
    if migration.table_exists("memory_base_workflow_run", conn):
        op.drop_index("ix_mbwr_ingestion_job_id", table_name="memory_base_workflow_run")
        op.drop_index("ix_mbwr_mb_session", table_name="memory_base_workflow_run")
        op.drop_table("memory_base_workflow_run")

    if migration.table_exists("message_ingestion_record", conn):
        op.drop_index("ix_mir_memory_base_session", table_name="message_ingestion_record")
        op.drop_index("ix_mir_job_id", table_name="message_ingestion_record")
        op.drop_index("ix_mir_message_id", table_name="message_ingestion_record")
        if conn.dialect.name == "postgresql":
            # Explicitly drop the constraint to unblock message table drop in prior migrations
            op.execute(
                'ALTER TABLE "message_ingestion_record" DROP CONSTRAINT IF EXISTS "fk_message_ingestion_record_message_id_message"'
            )
            op.execute('DROP TABLE "message_ingestion_record" CASCADE')
        else:
            op.drop_table("message_ingestion_record")

    if migration.table_exists("memory_base_session", conn):
        op.drop_index("ix_memory_base_session_lookup", table_name="memory_base_session")
        op.drop_index("ix_memory_base_session_session_id", table_name="memory_base_session")
        op.drop_index("ix_memory_base_session_memory_base_id", table_name="memory_base_session")
        op.drop_table("memory_base_session")

    if migration.table_exists("memory_base", conn):
        op.drop_index("ix_memory_base_user_id", table_name="memory_base")
        op.drop_index("ix_memory_base_flow_id", table_name="memory_base")
        op.drop_table("memory_base")

    # Message column/index ----------------------------------------------- #
    existing_message_indexes = {idx["name"] for idx in sa.inspect(conn).get_indexes("message")}
    if "ix_message_run_id" in existing_message_indexes:
        op.drop_index("ix_message_run_id", table_name="message")
    with op.batch_alter_table("message", schema=None) as batch_op:
        if migration.column_exists("message", "is_output", conn):
            batch_op.drop_column("is_output")
        if migration.column_exists("message", "run_id", conn):
            batch_op.drop_column("run_id")

    # Job column/index --------------------------------------------------- #
    with op.batch_alter_table("job", schema=None) as batch_op:
        existing_job_indexes = {idx["name"] for idx in sa.inspect(conn).get_indexes("job")}
        if "ix_job_dedupe_key" in existing_job_indexes:
            batch_op.drop_index(batch_op.f("ix_job_dedupe_key"))
        if migration.column_exists("job", "dedupe_key", conn):
            batch_op.drop_column("dedupe_key")
