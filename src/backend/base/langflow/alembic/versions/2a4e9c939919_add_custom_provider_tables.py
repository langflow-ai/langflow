"""Add custom_provider and custom_provider_model tables

Revision ID: 2a4e9c939919
Revises: 0e6138e7a0c2, 4e5980a44eaa
Create Date: 2026-04-02 00:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "2a4e9c939919"  # pragma: allowlist secret
down_revision: tuple[str, str] = ("0e6138e7a0c2", "4e5980a44eaa")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CUSTOM_PROVIDER_USER_NAME_UNIQUE_CONSTRAINT = "uq_custom_provider_user_name"
CUSTOM_PROVIDER_MODEL_PROVIDER_NAME_UNIQUE_CONSTRAINT = "uq_custom_provider_model_provider_name"


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("custom_provider", conn):
        op.create_table(
            "custom_provider",
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("user_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
            sa.Column("base_url", sqlmodel.sql.sqltypes.AutoString(length=2048), nullable=False),
            sa.Column("api_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["user.id"],
                name=op.f("fk_custom_provider_user_id_user"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_custom_provider")),
        )
        with op.batch_alter_table("custom_provider", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_custom_provider_user_id"), ["user_id"], unique=False)
            batch_op.create_unique_constraint(
                CUSTOM_PROVIDER_USER_NAME_UNIQUE_CONSTRAINT, ["user_id", "name"]
            )

    if not migration.table_exists("custom_provider_model", conn):
        op.create_table(
            "custom_provider_model",
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("provider_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
            sa.Column(
                "tool_calling",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["provider_id"],
                ["custom_provider.id"],
                name=op.f("fk_custom_provider_model_provider_id_custom_provider"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_custom_provider_model")),
        )
        with op.batch_alter_table("custom_provider_model", schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f("ix_custom_provider_model_provider_id"), ["provider_id"], unique=False
            )
            batch_op.create_unique_constraint(
                CUSTOM_PROVIDER_MODEL_PROVIDER_NAME_UNIQUE_CONSTRAINT, ["provider_id", "name"]
            )


def downgrade() -> None:
    conn = op.get_bind()

    if migration.table_exists("custom_provider_model", conn):
        with op.batch_alter_table("custom_provider_model", schema=None) as batch_op:
            batch_op.drop_constraint(CUSTOM_PROVIDER_MODEL_PROVIDER_NAME_UNIQUE_CONSTRAINT, type_="unique")
            batch_op.drop_index(batch_op.f("ix_custom_provider_model_provider_id"))
        op.drop_table("custom_provider_model")

    if migration.table_exists("custom_provider", conn):
        with op.batch_alter_table("custom_provider", schema=None) as batch_op:
            batch_op.drop_constraint(CUSTOM_PROVIDER_USER_NAME_UNIQUE_CONSTRAINT, type_="unique")
            batch_op.drop_index(batch_op.f("ix_custom_provider_user_id"))
        op.drop_table("custom_provider")
