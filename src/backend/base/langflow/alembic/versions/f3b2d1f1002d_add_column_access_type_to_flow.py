"""add column 'access_type' to flow

Revision ID: f3b2d1f1002d
Revises: 93e2705fa8d6
Create Date: 2025-02-05 14:35:29.658101

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = 'f3b2d1f1002d'
down_revision: Union[str, None] = '93e2705fa8d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table('flow', schema=None) as batch_op:
        if not migration.column_exists(table_name='flow', column_name='access_type', conn=conn):
            batch_op.add_column(sa.Column('access_type', sa.Enum('PRIVATE', 'PUBLIC', name='access_type_enum'), server_default='private', nullable=False))


def downgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table('flow', schema=None) as batch_op:
        if migration.column_exists(table_name='flow', column_name='access_type', conn=conn):
            batch_op.drop_column('access_type')
