"""Add session_metadata column to message table

Phase: EXPAND

Adds a flexible JSON column to store enterprise session context including
tenant_id, user_id, region, policies, retention profiles, and data flags.
This enables client-driven metadata injection for enterprise session management.

Revision ID: ef4b036b585d
Revises: 0e6138e7a0c2
Create Date: 2026-03-19 10:32:05.048791

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ef4b036b585d'
down_revision: Union[str, None] = '0e6138e7a0c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session_metadata', sa.JSON(), nullable=True))
    
    if conn.dialect.name == 'postgresql':
        op.create_index(
            'ix_message_session_metadata_tenant',
            'message',
            [sa.text("(session_metadata->>'tenant_id')")],
            postgresql_using='btree',
            if_not_exists=True
        )
        op.create_index(
            'ix_message_session_metadata_user',
            'message',
            [sa.text("(session_metadata->>'user_id')")],
            postgresql_using='btree',
            if_not_exists=True
        )


def downgrade() -> None:
    conn = op.get_bind()
    
    if conn.dialect.name == 'postgresql':
        op.drop_index('ix_message_session_metadata_user', table_name='message', if_exists=True)
        op.drop_index('ix_message_session_metadata_tenant', table_name='message', if_exists=True)
    
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.drop_column('session_metadata')
