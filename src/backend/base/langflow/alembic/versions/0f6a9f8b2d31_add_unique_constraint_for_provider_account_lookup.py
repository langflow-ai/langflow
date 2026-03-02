"""add unique constraint for provider account lookup

Revision ID: 0f6a9f8b2d31
Revises: e0265ca70a45
Create Date: 2026-02-26 00:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "0f6a9f8b2d31"  # pragma: allowlist secret
down_revision: str | None = "e0265ca70a45"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UNIQUE_CONSTRAINT_NAME = "uq_deployment_provider_account_user_url_account"
TABLE_NAME = "deployment_provider_account"


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if migration.constraint_exists(TABLE_NAME, UNIQUE_CONSTRAINT_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.create_unique_constraint(UNIQUE_CONSTRAINT_NAME, ["user_id", "backend_url", "account_id"])


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if not migration.constraint_exists(TABLE_NAME, UNIQUE_CONSTRAINT_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.drop_constraint(UNIQUE_CONSTRAINT_NAME, type_="unique")
