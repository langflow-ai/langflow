"""Create memory tables

Revision ID: e5f6g7h8i9j0
Revises: 58b28437a398
Create Date: 2025-02-08 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "e5f6g7h8i9j0"
down_revision: str | None = "58b28437a398"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create the memory table
    if not migration.table_exists("memory", conn):
        op.create_table(
            "memory",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("kb_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("embedding_model", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("embedding_provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column(
                "status",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default="idle",
            ),
            sa.Column("error_message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("total_messages_processed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_chunks", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sessions_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_generated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("flow_id", sa.Uuid(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.ForeignKeyConstraint(["flow_id"], ["flow.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "flow_id", "name", name="unique_memory_name_per_user_flow"),
        )
        op.create_index(op.f("ix_memory_name"), "memory", ["name"], unique=False)
        op.create_index(op.f("ix_memory_flow_id"), "memory", ["flow_id"], unique=False)

    # Create the memoryprocessedmessage table
    if not migration.table_exists("memoryprocessedmessage", conn):
        op.create_table(
            "memoryprocessedmessage",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("memory_id", sa.Uuid(), nullable=False),
            sa.Column("message_id", sa.Uuid(), nullable=False),
            sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.ForeignKeyConstraint(["memory_id"], ["memory.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("memory_id", "message_id", name="unique_memory_message"),
        )
        op.create_index(
            op.f("ix_memoryprocessedmessage_memory_id"),
            "memoryprocessedmessage",
            ["memory_id"],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()

    if migration.table_exists("memoryprocessedmessage", conn):
        op.drop_index(op.f("ix_memoryprocessedmessage_memory_id"), table_name="memoryprocessedmessage")
        op.drop_table("memoryprocessedmessage")

    if migration.table_exists("memory", conn):
        op.drop_index(op.f("ix_memory_flow_id"), table_name="memory")
        op.drop_index(op.f("ix_memory_name"), table_name="memory")
        op.drop_table("memory")
