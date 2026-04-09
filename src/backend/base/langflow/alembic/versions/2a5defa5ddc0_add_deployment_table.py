"""Add deployment table

Revision ID: 2a5defa5ddc0
Revises: 8106300be7aa
Create Date: 2026-03-03 12:01:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "2a5defa5ddc0"  # pragma: allowlist secret
down_revision: str | None = "8106300be7aa"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME_UNIQUE_CONSTRAINT = "uq_deployment_name_in_provider"
RESOURCE_KEY_UNIQUE_CONSTRAINT = "uq_deployment_resource_key_in_provider"


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists("deployment", conn):
        return

    op.create_table(
        "deployment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resource_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("deployment_provider_account_id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["folder.id"],
            name=op.f("fk_deployment_project_id_folder"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["deployment_provider_account_id"],
            ["deployment_provider_account.id"],
            name=op.f("fk_deployment_deployment_provider_account_id_deployment_provider_account"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_deployment_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deployment")),
    )
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_deployment_name"), ["name"], unique=False)
        batch_op.create_index(batch_op.f("ix_deployment_project_id"), ["project_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_deployment_deployment_provider_account_id"),
            ["deployment_provider_account_id"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_deployment_resource_key"), ["resource_key"], unique=False)
        batch_op.create_index(batch_op.f("ix_deployment_user_id"), ["user_id"], unique=False)
        batch_op.create_unique_constraint(NAME_UNIQUE_CONSTRAINT, ["deployment_provider_account_id", "name"])
        batch_op.create_unique_constraint(
            RESOURCE_KEY_UNIQUE_CONSTRAINT, ["deployment_provider_account_id", "resource_key"]
        )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("deployment", conn):
        return

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_constraint(RESOURCE_KEY_UNIQUE_CONSTRAINT, type_="unique")
        batch_op.drop_constraint(NAME_UNIQUE_CONSTRAINT, type_="unique")
        batch_op.drop_index(batch_op.f("ix_deployment_user_id"))
        batch_op.drop_index(batch_op.f("ix_deployment_resource_key"))
        batch_op.drop_index(batch_op.f("ix_deployment_deployment_provider_account_id"))
        batch_op.drop_index(batch_op.f("ix_deployment_project_id"))
        batch_op.drop_index(batch_op.f("ix_deployment_name"))

    op.drop_table("deployment")
