"""add text annotation tables

Revision ID: ta1a2b3c4d5e
Revises: ia1a2b3c4d5e
Create Date: 2026-07-21

Phase: EXPAND
Safe to rollback: YES (drops only the two new tables)
Services compatible: old services never touch the new tables; new services
    404 until the tables exist.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlalchemy import JSON, func
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "ta1a2b3c4d5e"  # pragma: allowlist secret
down_revision: str | None = "ia1a2b3c4d5e"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Keep in sync with ``JsonVariant`` in
# ``langflow.services.database.models.text_annotation.model``.
JsonVariant = JSON().with_variant(JSONB(), "postgresql")

PROJECT_TABLE = "text_annotation_project"
TASK_TABLE = "text_annotation_task"


def upgrade() -> None:
    conn = op.get_bind()

    if not migration.table_exists(PROJECT_TABLE, conn):
        op.create_table(
            PROJECT_TABLE,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("task_type", sa.String(), nullable=False),
            sa.Column("entity_labels", JsonVariant, nullable=False),
            sa.Column("category_labels", JsonVariant, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
            sa.ForeignKeyConstraint(
                ["user_id"], ["user.id"], name="fk_text_annotation_project_user_id_user", ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id", name="pk_text_annotation_project"),
            sa.UniqueConstraint("user_id", "name", name="uq_text_annotation_project_user_name"),
        )
        op.create_index("ix_text_annotation_project_user_id", PROJECT_TABLE, ["user_id"])
        op.create_index("ix_text_annotation_project_name", PROJECT_TABLE, ["name"])

    if not migration.table_exists(TASK_TABLE, conn):
        op.create_table(
            TASK_TABLE,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("result", JsonVariant, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
            sa.ForeignKeyConstraint(
                ["project_id"],
                ["text_annotation_project.id"],
                name="fk_text_annotation_task_project_id",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["user.id"], name="fk_text_annotation_task_user_id_user", ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id", name="pk_text_annotation_task"),
        )
        op.create_index("ix_text_annotation_task_project_id", TASK_TABLE, ["project_id"])
        op.create_index("ix_text_annotation_task_user_id", TASK_TABLE, ["user_id"])


def downgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TASK_TABLE, conn):
        op.drop_table(TASK_TABLE)
    if migration.table_exists(PROJECT_TABLE, conn):
        op.drop_table(PROJECT_TABLE)
