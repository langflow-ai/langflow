"""Add deployment provider account table

Revision ID: a1b2c3d4e5f6
Revises: 3478f0bd6ccb
Create Date: 2026-03-03 00:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlmodel.sql.sqltypes import AutoString

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"  # pragma: allowlist secret
down_revision: str | None = "3478f0bd6ccb"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "deployment_provider_account"
UNIQUE_CONSTRAINT_NAME = "uq_deployment_provider_account_user_url_account"


def upgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", AutoString(), nullable=True),
        sa.Column("provider_key", AutoString(), nullable=False),
        sa.Column("backend_url", AutoString(), nullable=False),
        sa.Column("api_key", AutoString(), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name=op.f("fk_deployment_provider_account_user_id_user")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deployment_provider_account")),
        sa.UniqueConstraint("user_id", "backend_url", "account_id", name=UNIQUE_CONSTRAINT_NAME),
    )

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_deployment_provider_account_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_deployment_provider_account_account_id"), ["account_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_deployment_provider_account_provider_key"), ["provider_key"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_deployment_provider_account_provider_key"))
        batch_op.drop_index(batch_op.f("ix_deployment_provider_account_account_id"))
        batch_op.drop_index(batch_op.f("ix_deployment_provider_account_user_id"))

    op.drop_table(TABLE_NAME)
