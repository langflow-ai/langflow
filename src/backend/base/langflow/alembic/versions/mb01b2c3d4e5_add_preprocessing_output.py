"""add_preprocessing_output

Adds:
  - memory_base.preproc_kill_phrase (nullable String) to support LLM gating sentinel.
  - memory_base_preprocessing_output table — one row per preprocessing batch capturing
    the LLM output, status (processed/ingested/skipped), and the source message-id list
    so two-phase commit (LLM call → Chroma write) can resume after KB failures.

Phase: EXPAND

Revision ID: mb01b2c3d4e5
Revises: kb1a2b3c4d5e
Create Date: 2026-05-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "mb01b2c3d4e5"  # pragma: allowlist secret
down_revision: str | None = "kb1a2b3c4d5e"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------ #
    #  memory_base.preproc_kill_phrase                                     #
    # ------------------------------------------------------------------ #
    with op.batch_alter_table("memory_base", schema=None) as batch_op:
        if not migration.column_exists("memory_base", "preproc_kill_phrase", conn):
            batch_op.add_column(sa.Column("preproc_kill_phrase", sa.String(), nullable=True))

    # ------------------------------------------------------------------ #
    #  memory_base_preprocessing_output                                    #
    # ------------------------------------------------------------------ #
    if not migration.table_exists("memory_base_preprocessing_output", conn):
        op.create_table(
            "memory_base_preprocessing_output",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column(
                "memory_base_id",
                sa.Uuid(),
                sa.ForeignKey("memory_base.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("session_id", sa.String(), nullable=False),
            sa.Column(
                "job_id",
                sa.Uuid(),
                sa.ForeignKey("job.job_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("output_text", sa.Text(), nullable=True),
            sa.Column("source_message_ids", sa.JSON(), nullable=False),
            sa.Column("model_used", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_mbpo_pending",
            "memory_base_preprocessing_output",
            ["memory_base_id", "session_id", "status", "created_at"],
        )
        op.create_index(
            "ix_mbpo_listing",
            "memory_base_preprocessing_output",
            ["memory_base_id", "session_id", "created_at"],
        )
        op.create_index(
            "ix_mbpo_job_id",
            "memory_base_preprocessing_output",
            ["job_id"],
        )


def downgrade() -> None:
    conn = op.get_bind()

    if migration.table_exists("memory_base_preprocessing_output", conn):
        op.drop_index("ix_mbpo_job_id", table_name="memory_base_preprocessing_output")
        op.drop_index("ix_mbpo_listing", table_name="memory_base_preprocessing_output")
        op.drop_index("ix_mbpo_pending", table_name="memory_base_preprocessing_output")
        op.drop_table("memory_base_preprocessing_output")

    with op.batch_alter_table("memory_base", schema=None) as batch_op:
        if migration.column_exists("memory_base", "preproc_kill_phrase", conn):
            batch_op.drop_column("preproc_kill_phrase")
