"""add column 'public' to flow

Revision ID: af9e9e93cd24
Revises: e3162c1804e6
Create Date: 2025-02-05 08:47:28.267033

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = 'af9e9e93cd24'
down_revision: Union[str, None] = 'e3162c1804e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table('flow', schema=None) as batch_op:
        if not migration.column_exists(table_name='flow', column_name='public', conn=conn):
            batch_op.add_column(sa.Column('public', sa.Boolean(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table('flow', schema=None) as batch_op:
        if migration.column_exists(table_name='flow', column_name='public', conn=conn):
            batch_op.drop_column('public')
