"""add deployment provider account table.

Revision ID: 6fbba5893c57
Revises: 369268b9af8b
Create Date: 2026-02-20 00:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

# revision identifiers, used by Alembic.
revision: str = "6fbba5893c57"  # pragma: allowlist secret
down_revision: str | None = "369268b9af8b"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if migration.table_exists("deployment_provider_account", conn):
        return

    op.create_table(
        "deployment_provider_account",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", AutoString(), nullable=False),
        sa.Column("provider_key", AutoString(), nullable=False),
        sa.Column("backend_url", AutoString(), nullable=False),
        sa.Column("api_key", AutoString(), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name=op.f("fk_deployment_provider_account_user_id_user")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deployment_provider_account")),
    )

    with op.batch_alter_table("deployment_provider_account", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_deployment_provider_account_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_deployment_provider_account_account_id"), ["account_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_deployment_provider_account_provider_key"), ["provider_key"], unique=False)


def downgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if not migration.table_exists("deployment_provider_account", conn):
        return

    with op.batch_alter_table("deployment_provider_account", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_deployment_provider_account_provider_key"))
        batch_op.drop_index(batch_op.f("ix_deployment_provider_account_account_id"))
        batch_op.drop_index(batch_op.f("ix_deployment_provider_account_user_id"))

    op.drop_table("deployment_provider_account")
