"""add ondelete cascade to span fks

Revision ID: e205cdf2b74b
Revises: d306e5c17c41
Create Date: 2026-04-16 13:10:51.407006

Phase: EXPAND

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = 'e205cdf2b74b'
down_revision: Union[str, None] = 'd306e5c17c41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_fk_constraint_name(conn, table_name: str, column_name: str) -> str | None:
    """Find the foreign key constraint name for a given column."""
    inspector = sa.inspect(conn)
    for fk in inspector.get_foreign_keys(table_name):
        if column_name in fk["constrained_columns"]:
            return fk["name"]
    return None


def upgrade() -> None:
    conn = op.get_bind()

    if not migration.table_exists("span", conn):
        return

    trace_fk_name = _get_fk_constraint_name(conn, "span", "trace_id")
    parent_fk_name = _get_fk_constraint_name(conn, "span", "parent_span_id")

    with op.batch_alter_table('span', schema=None) as batch_op:
        if trace_fk_name is not None:
            batch_op.drop_constraint(trace_fk_name, type_='foreignkey')
        if parent_fk_name is not None:
            batch_op.drop_constraint(parent_fk_name, type_='foreignkey')
        batch_op.create_foreign_key('fk_span_parent_span_id_span', 'span', ['parent_span_id'], ['id'], ondelete='CASCADE')
        batch_op.create_foreign_key('fk_span_trace_id_trace', 'trace', ['trace_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    conn = op.get_bind()

    if not migration.table_exists("span", conn):
        return

    trace_fk_name = _get_fk_constraint_name(conn, "span", "trace_id")
    parent_fk_name = _get_fk_constraint_name(conn, "span", "parent_span_id")

    with op.batch_alter_table('span', schema=None) as batch_op:
        if trace_fk_name is not None:
            batch_op.drop_constraint(trace_fk_name, type_='foreignkey')
        if parent_fk_name is not None:
            batch_op.drop_constraint(parent_fk_name, type_='foreignkey')
        batch_op.create_foreign_key('fk_span_parent_span_id_span', 'span', ['parent_span_id'], ['id'])
        batch_op.create_foreign_key('fk_span_trace_id_trace', 'trace', ['trace_id'], ['id'])
