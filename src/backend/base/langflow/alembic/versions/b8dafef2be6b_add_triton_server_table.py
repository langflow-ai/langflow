"""Add triton server table

Revision ID: b8dafef2be6b
Revises: b7c4d8e9f012
Create Date: 2026-07-06 00:00:00.000000

Phase: EXPAND

Stores per-user NVIDIA Triton Inference Server endpoint configurations
(name, base_url, optional encrypted auth_token, notes). Used by the
Langflow frontend Triton management page to manage server connections;
actual Triton API calls are made by the frontend through the user's own
reverse proxy, not by the Langflow backend.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlmodel.sql.sqltypes import AutoString

revision: str = "b8dafef2be6b"  # pragma: allowlist secret
down_revision: str | None = "b7c4d8e9f012"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "triton_server"
UNIQUE_CONSTRAINT_NAME = "uq_triton_server_user_name"


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", AutoString(), nullable=False),
        sa.Column("base_url", AutoString(), nullable=False),
        sa.Column("auth_token", AutoString(), nullable=True),
        sa.Column("notes", AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_triton_server_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_triton_server")),
        sa.UniqueConstraint("user_id", "name", name=UNIQUE_CONSTRAINT_NAME),
    )

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_triton_server_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_triton_server_user_id"))

    op.drop_table(TABLE_NAME)
