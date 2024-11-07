"""add persistent locked state

Revision ID: e3162c1804e6
Revises: 1eab2c3eb45e
Create Date: 2024-11-07 14:50:35.201760

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = 'e3162c1804e6'
down_revision: Union[str, None] = '1eab2c3eb45e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table('flow', schema=None) as batch_op:
        if not migration.column_exists(table_name='flow', column_name='locked', conn=conn):
            batch_op.add_column(sa.Column('locked', sa.Boolean(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table('flow', schema=None) as batch_op:
        if migration.column_exists(table_name='flow', column_name='locked', conn=conn):
            batch_op.drop_column('locked')
