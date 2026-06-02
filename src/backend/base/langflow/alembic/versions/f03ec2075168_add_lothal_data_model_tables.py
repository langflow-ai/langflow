"""add lothal data model tables

Revision ID: f03ec2075168
Revises: d306e5c17c41
Create Date: 2026-06-02 21:17:29.056071

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = 'f03ec2075168'
down_revision: Union[str, None] = 'd306e5c17c41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    if 'lothal_project' not in existing_tables:
        op.create_table(
            'lothal_project',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('user_id', sa.Uuid(), nullable=False),
            sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('phase', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('prd_content', sa.Text(), nullable=True),
            sa.Column('diagram_mmd', sa.Text(), nullable=True),
            sa.Column('diagram_layout', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
            sa.PrimaryKeyConstraint('id'),
        )
        with op.batch_alter_table('lothal_project', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_lothal_project_name'), ['name'], unique=False)
            batch_op.create_index(batch_op.f('ix_lothal_project_user_id'), ['user_id'], unique=False)

    if 'lothal_message' not in existing_tables:
        op.create_table(
            'lothal_message',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('project_id', sa.Uuid(), nullable=False),
            sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('suggestions', sa.JSON(), nullable=True),
            sa.Column('phase', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['lothal_project.id'], ),
            sa.PrimaryKeyConstraint('id'),
        )
        with op.batch_alter_table('lothal_message', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_lothal_message_project_id'), ['project_id'], unique=False)

    if 'lothal_code_file' not in existing_tables:
        op.create_table(
            'lothal_code_file',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('project_id', sa.Uuid(), nullable=False),
            sa.Column('path', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['lothal_project.id'], ),
            sa.PrimaryKeyConstraint('id'),
        )
        with op.batch_alter_table('lothal_code_file', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_lothal_code_file_project_id'), ['project_id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    if 'lothal_code_file' in existing_tables:
        with op.batch_alter_table('lothal_code_file', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_lothal_code_file_project_id'))
        op.drop_table('lothal_code_file')

    if 'lothal_message' in existing_tables:
        with op.batch_alter_table('lothal_message', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_lothal_message_project_id'))
        op.drop_table('lothal_message')

    if 'lothal_project' in existing_tables:
        with op.batch_alter_table('lothal_project', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_lothal_project_user_id'))
            batch_op.drop_index(batch_op.f('ix_lothal_project_name'))
        op.drop_table('lothal_project')
