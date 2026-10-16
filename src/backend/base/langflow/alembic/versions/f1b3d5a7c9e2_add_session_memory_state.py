"""Add session_memory_state for rolling chat-history summaries.

Revision ID: f1b3d5a7c9e2
Revises: e5a7c9b1d3f2
Phase: EXPAND
Safe to rollback: YES (the summaries are a derived cache of the messages)
Services compatible: Older versions ignore this additional table.
"""

import sqlalchemy as sa
from alembic import op

revision = "f1b3d5a7c9e2"  # pragma: allowlist secret - Alembic revision
down_revision = "e5a7c9b1d3f2"  # pragma: allowlist secret - Alembic revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("session_memory_state"):
        return
    op.create_table(
        "session_memory_state",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("flow_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("context_id", sa.String(), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("cursor_message_id", sa.Uuid(), nullable=True),
        sa.Column("cursor_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("folded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary_model", sa.String(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("flow_id", "user_id", "session_id", "context_id", name="uq_session_memory_state_scope"),
    )
    op.create_index("ix_session_memory_state_flow_session", "session_memory_state", ["flow_id", "session_id"])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("session_memory_state"):
        op.drop_table("session_memory_state")
