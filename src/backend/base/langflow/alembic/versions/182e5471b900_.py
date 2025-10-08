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
    # Add context_id column to message table
    op.add_column('message', sa.Column('context_id', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove context_id column from message table
    op.drop_column('message', 'context_id')
