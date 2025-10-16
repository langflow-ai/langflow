"""add context_id to message table

Revision ID: 182e5471b900
Revises: d37bc4322900
Create Date: 2025-10-08 11:30:12.912190

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '182e5471b900'
down_revision: Union[str, None] = 'd37bc4322900'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if context_id column already exists
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('message')]
    
    # Add context_id column if it does not exist
    if 'context_id' not in columns:
        op.add_column('message', sa.Column('context_id', sa.String(), nullable=True))


def downgrade() -> None:
    # Check if context_id column exists before dropping
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('message')]
    
    # Drop context_id column if it exists
    if 'context_id' in columns:
        op.drop_column('message', 'context_id')
