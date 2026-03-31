"""add_memory_base_tables

Phase: EXPAND

Creates:
  - memory_base table
  - memory_base_session table (FK inline on column, matching SQLModel output)

Adds to message table:
  - message.run_id  (nullable UUID, indexed)
  - message.is_output (bool, default False)

Merges heads: 36aa87831162, 8255e9fc18d9

Revision ID: c1d2e3f4a5b6
Revises: 36aa87831162, 8255e9fc18d9
Create Date: 2026-03-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = (
    "36aa87831162",
    "8255e9fc18d9",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------ #
    #  memory_base                                                          #
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
        )
        op.create_index("ix_memory_base_flow_id", "memory_base", ["flow_id"])
        op.create_index("ix_memory_base_user_id", "memory_base", ["user_id"])

    # ------------------------------------------------------------------ #
    #  memory_base_session                                                  #
    # ------------------------------------------------------------------ #
    if not migration.table_exists("memory_base_session", conn):
        op.create_table(
            "memory_base_session",
            sa.Column("id", sa.Uuid(), nullable=False),
            # FK defined inline on the column — matches SQLModel Field(sa_column=Column(..., ForeignKey(...)))
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
    #  message extensions                                                   #
    # ------------------------------------------------------------------ #
    with op.batch_alter_table("message", schema=None) as batch_op:
        if not migration.column_exists("message", "run_id", conn):
            batch_op.add_column(sa.Column("run_id", sa.Uuid(), nullable=True))
        if not migration.column_exists("message", "is_output", conn):
            batch_op.add_column(sa.Column("is_output", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    try:
        op.create_index("ix_message_run_id", "message", ["run_id"])
    except Exception:
        pass  # Index may already exist in a re-run scenario


def downgrade() -> None:
    conn = op.get_bind()

    # Drop message extensions
    try:
        op.drop_index("ix_message_run_id", table_name="message")
    except Exception:
        pass  # Index may not exist if upgrade was partial
    with op.batch_alter_table("message", schema=None) as batch_op:
        if migration.column_exists("message", "is_output", conn):
            batch_op.drop_column("is_output")
        if migration.column_exists("message", "run_id", conn):
            batch_op.drop_column("run_id")

    # Drop memory_base_session first (FK dependency)
    if migration.table_exists("memory_base_session", conn):
        op.drop_index("ix_memory_base_session_lookup", table_name="memory_base_session")
        op.drop_index("ix_memory_base_session_session_id", table_name="memory_base_session")
        op.drop_index("ix_memory_base_session_memory_base_id", table_name="memory_base_session")
        op.drop_table("memory_base_session")

    # Drop memory_base
    if migration.table_exists("memory_base", conn):
        op.drop_index("ix_memory_base_user_id", table_name="memory_base")
        op.drop_index("ix_memory_base_flow_id", table_name="memory_base")
        op.drop_table("memory_base")
