"""Add ondelete CASCADE to file.user_id FK

Revision ID: 0e6138e7a0c2
Revises: fc7f696a57bf
Create Date: 2026-03-11 13:28:25.239444

Phase: EXPAND
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = "0e6138e7a0c2"  # pragma: allowlist secret
down_revision: str | None = "fc7f696a57bf"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _get_fk_constraint_name(conn, table_name: str, column_name: str) -> str | None:
    """Find the foreign key constraint name for a given column."""
    inspector = sa.inspect(conn)
    for fk in inspector.get_foreign_keys(table_name):
        if column_name in fk["constrained_columns"]:
            return fk["name"]
    return None


def upgrade() -> None:
    conn = op.get_bind()

    if not migration.table_exists("file", conn):
        return

    fk_name = _get_fk_constraint_name(conn, "file", "user_id")

    if fk_name is None:
        with op.batch_alter_table('file', schema=None) as batch_op:
            batch_op.create_foreign_key(
                "fk_file_user_id_user", 'user', ['user_id'], ['id'], ondelete='CASCADE'
            )
    else:
        with op.batch_alter_table('file', schema=None) as batch_op:
            batch_op.drop_constraint(fk_name, type_='foreignkey')
            batch_op.create_foreign_key(
                "fk_file_user_id_user", 'user', ['user_id'], ['id'], ondelete='CASCADE'
            )


def downgrade() -> None:
    conn = op.get_bind()

    if not migration.table_exists("file", conn):
        return

    fk_name = _get_fk_constraint_name(conn, "file", "user_id")

    if fk_name is None:
        return

    with op.batch_alter_table('file', schema=None) as batch_op:
        batch_op.drop_constraint(fk_name, type_='foreignkey')
        batch_op.create_foreign_key(
            "fk_file_user_id_user", 'user', ['user_id'], ['id']
        )
