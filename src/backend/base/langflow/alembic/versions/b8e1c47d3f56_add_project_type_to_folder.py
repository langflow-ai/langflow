"""add project_type and project_config to folder

Revision ID: b8e1c47d3f56
Revises: a3f8b1c9d7e2
Create Date: 2026-08-21 10:00:00.000000

Phase: EXPAND

``project_type`` is deliberately ``sa.Text``, matching the model's ``Column(Text)``, and not
``sa.Enum``. A DB enum would need an ``ALTER TYPE ... ADD VALUE`` migration for every new
project type, which is the cost ``deployment_type_enum`` already pays. The set of valid values
is enforced in the application by ``folder.utils.validate_project_type``, not by the database.

No data pass. Every existing row takes the server default.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "b8e1c47d3f56"  # pragma: allowlist secret
down_revision: str | None = "a3f8b1c9d7e2"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("folder", schema=None) as batch_op:
        if not migration.column_exists(table_name="folder", column_name="project_type", conn=conn):
            batch_op.add_column(sa.Column("project_type", sa.Text(), server_default=sa.text("'flows'"), nullable=False))
        if not migration.column_exists(table_name="folder", column_name="project_config", conn=conn):
            batch_op.add_column(sa.Column("project_config", sa.JSON(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("folder", schema=None) as batch_op:
        if migration.column_exists(table_name="folder", column_name="project_config", conn=conn):
            batch_op.drop_column("project_config")
        if migration.column_exists(table_name="folder", column_name="project_type", conn=conn):
            batch_op.drop_column("project_type")
