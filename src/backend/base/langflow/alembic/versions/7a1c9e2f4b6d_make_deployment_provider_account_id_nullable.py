"""make deployment provider account_id nullable

Revision ID: 7a1c9e2f4b6d
Revises: 6fbba5893c57
Create Date: 2026-02-20 17:36:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "7a1c9e2f4b6d"  # pragma: allowlist secret
down_revision: str | None = "6fbba5893c57"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("deployment_provider_account", conn):
        return
    if not migration.column_exists("deployment_provider_account", "account_id", conn):
        return

    inspector = sa.inspect(conn)  # type: ignore[arg-type]
    columns = inspector.get_columns("deployment_provider_account")
    account_id_column = next((column for column in columns if column["name"] == "account_id"), None)
    if account_id_column is None or account_id_column.get("nullable", False):
        return

    with op.batch_alter_table("deployment_provider_account", schema=None) as batch_op:
        batch_op.alter_column("account_id", existing_type=sa.VARCHAR(), nullable=True)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("deployment_provider_account", conn):
        return
    if not migration.column_exists("deployment_provider_account", "account_id", conn):
        return

    inspector = sa.inspect(conn)  # type: ignore[arg-type]
    columns = inspector.get_columns("deployment_provider_account")
    account_id_column = next((column for column in columns if column["name"] == "account_id"), None)
    if account_id_column is None or not account_id_column.get("nullable", True):
        return

    with op.batch_alter_table("deployment_provider_account", schema=None) as batch_op:
        batch_op.alter_column("account_id", existing_type=sa.VARCHAR(), nullable=False)
