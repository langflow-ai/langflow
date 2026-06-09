"""Add ondelete CASCADE to lothal foreign keys

Revision ID: f2e57d2327a2
Revises: f03ec2075168
Create Date: 2026-06-09 19:40:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "f2e57d2327a2"  # pragma: allowlist secret
down_revision: str | None = "f03ec2075168"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, column, referred table, replacement constraint name). The original
# constraints were created unnamed by f03ec2075168, so each is looked up by
# inspection before being replaced with a named CASCADE constraint.
_FKS = [
    ("lothal_project", "user_id", "user", "fk_lothal_project_user_id_user"),
    ("lothal_message", "project_id", "lothal_project", "fk_lothal_message_project_id_lothal_project"),
    ("lothal_code_file", "project_id", "lothal_project", "fk_lothal_code_file_project_id_lothal_project"),
]


def _get_fk_constraint_name(conn, table_name: str, column_name: str) -> str | None:
    """Find the foreign key constraint name for a given column."""
    inspector = sa.inspect(conn)
    for fk in inspector.get_foreign_keys(table_name):
        if column_name in fk["constrained_columns"]:
            return fk["name"]
    return None


def upgrade() -> None:
    conn = op.get_bind()

    for table, column, referred, name in _FKS:
        if not migration.table_exists(table, conn):
            continue

        fk_name = _get_fk_constraint_name(conn, table, column)

        with op.batch_alter_table(table, schema=None) as batch_op:
            if fk_name is not None:
                batch_op.drop_constraint(fk_name, type_="foreignkey")
            batch_op.create_foreign_key(name, referred, [column], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    conn = op.get_bind()

    for table, column, referred, name in _FKS:
        if not migration.table_exists(table, conn):
            continue

        fk_name = _get_fk_constraint_name(conn, table, column)
        if fk_name is None:
            continue

        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
            batch_op.create_foreign_key(name, referred, [column], ["id"])
