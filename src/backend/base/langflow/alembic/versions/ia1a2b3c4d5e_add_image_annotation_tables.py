"""add image annotation tables

Revision ID: ia1a2b3c4d5e
Revises: 7ab3c4d5e6f7
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

revision: str = "ia1a2b3c4d5e"  # pragma: allowlist secret
down_revision: str | None = "7ab3c4d5e6f7"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Keep in sync with ``JsonVariant`` in
# ``langflow.services.database.models.annotation.model``.
JsonVariant = JSON().with_variant(JSONB(), "postgresql")

PROJECT_TABLE = "annotation_project"
IMAGE_TABLE = "annotation_image"


def upgrade() -> None:
    conn = op.get_bind()

    if not migration.table_exists(PROJECT_TABLE, conn):
        op.create_table(
            PROJECT_TABLE,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("labels", JsonVariant, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
            sa.ForeignKeyConstraint(
                ["user_id"], ["user.id"], name="fk_annotation_project_user_id_user", ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id", name="pk_annotation_project"),
            sa.UniqueConstraint("user_id", "name", name="uq_annotation_project_user_name"),
        )
        op.create_index("ix_annotation_project_user_id", PROJECT_TABLE, ["user_id"])
        op.create_index("ix_annotation_project_name", PROJECT_TABLE, ["name"])

    if not migration.table_exists(IMAGE_TABLE, conn):
        op.create_table(
            IMAGE_TABLE,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("path", sa.String(), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("width", sa.Integer(), nullable=True),
            sa.Column("height", sa.Integer(), nullable=True),
            sa.Column("result", JsonVariant, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
            sa.ForeignKeyConstraint(
                ["project_id"], ["annotation_project.id"], name="fk_annotation_image_project_id", ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["user.id"], name="fk_annotation_image_user_id_user", ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id", name="pk_annotation_image"),
        )
        op.create_index("ix_annotation_image_project_id", IMAGE_TABLE, ["project_id"])
        op.create_index("ix_annotation_image_user_id", IMAGE_TABLE, ["user_id"])


def downgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(IMAGE_TABLE, conn):
        op.drop_table(IMAGE_TABLE)
    if migration.table_exists(PROJECT_TABLE, conn):
        op.drop_table(PROJECT_TABLE)
