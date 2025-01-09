"""update job table

Revision ID: 1ea1b79fcfbb
Revises: a6faa131285d
Create Date: 2024-12-24 10:34:32.634735

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.engine.reflection import Inspector

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = '1ea1b79fcfbb'
down_revision: Union[str, None] = 'a6faa131285d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)  # type: ignore
    table_names = inspector.get_table_names()

    if "job" in table_names:
        with op.batch_alter_table('job', schema=None) as batch_op:
            if not migration.column_exists('job', 'status', conn):
                batch_op.add_column(sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False))
            if not migration.column_exists('job', 'result', conn):
                batch_op.add_column(sa.Column('result', sa.JSON(), nullable=True))
            if not migration.column_exists('job', 'error', conn):
                batch_op.add_column(sa.Column('error', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
            fks = inspector.get_foreign_keys('job')
            for fk in fks:
                if fk['name'] == 'fk_job_flow_id_flow':
                    batch_op.drop_constraint('fk_job_flow_id_flow', type_='foreignkey')
                if fk['name'] == 'fk_job_user_id_user':
                    batch_op.drop_constraint('fk_job_user_id_user', type_='foreignkey')

            batch_op.create_foreign_key('fk_job_flow_id_flow_new', 'flow', ['flow_id'], ['id'])
            batch_op.create_foreign_key('fk_job_user_id_user_new', 'user', ['user_id'], ['id'])

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)  # type: ignore
    table_names = inspector.get_table_names()

    if "job" in table_names:
        with op.batch_alter_table('job', schema=None) as batch_op:
            if migration.column_exists('job', 'error', conn):
                batch_op.drop_column('error')
            if migration.column_exists('job', 'result', conn):
                batch_op.drop_column('result')
            if migration.column_exists('job', 'status', conn):
                batch_op.drop_column('status')
            fks = inspector.get_foreign_keys('job')
            for fk in fks:
                if fk['name'] == 'fk_job_flow_id_flow_new':
                    batch_op.drop_constraint('fk_job_flow_id_flow_new', type_='foreignkey')
                if fk['name'] == 'fk_job_user_id_user_new':
                    batch_op.drop_constraint('fk_job_user_id_user_new', type_='foreignkey')

            batch_op.create_foreign_key('fk_job_user_id_user', 'user', ['user_id'], ['id'], ondelete='CASCADE')
            batch_op.create_foreign_key('fk_job_flow_id_flow', 'flow', ['flow_id'], ['id'], ondelete='CASCADE')
