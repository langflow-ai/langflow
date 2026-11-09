"""Keep the original Project name on pruned replacement receipts.

Revision ID: 7fd2c80e5a39
Revises: d8e9f0a1b2c3
Phase: EXPAND
"""

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision = "7fd2c80e5a39"  # pragma: allowlist secret
down_revision = "d8e9f0a1b2c3"  # pragma: allowlist secret
branch_labels = None
depends_on = None

_TABLE = "project_replacement_operation"


def upgrade() -> None:
    if not migration.column_exists(_TABLE, "project_name", op.get_bind()):
        op.add_column(_TABLE, sa.Column("project_name", sa.String(), nullable=True))


def downgrade() -> None:
    if migration.column_exists(_TABLE, "project_name", op.get_bind()):
        op.drop_column(_TABLE, "project_name")
