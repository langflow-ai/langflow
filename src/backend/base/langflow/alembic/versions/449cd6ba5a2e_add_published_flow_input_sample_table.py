"""Add published_flow_input_sample table

Revision ID: 449cd6ba5a2e
Revises: 20251107000000
Create Date: 2025-11-11 10:29:40.151218

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '449cd6ba5a2e'
down_revision: Union[str, None] = '20251107000000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create published_flow_input_sample table to store sample inputs/outputs."""
    # Create the new table
    op.create_table(
        'published_flow_input_sample',
        sa.Column('storage_account', sa.Text(), nullable=True),
        sa.Column('container_name', sa.Text(), nullable=True),
        sa.Column('file_names', sa.JSON(), nullable=True),
        sa.Column('sample_text', sa.JSON(), nullable=True),
        sa.Column('sample_output', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('published_flow_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['published_flow_id'], ['published_flow.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index on foreign key
    with op.batch_alter_table('published_flow_input_sample', schema=None) as batch_op:
        batch_op.create_index(
            'ix_published_flow_input_sample_published_flow_id',
            ['published_flow_id'],
            unique=False
        )


def downgrade() -> None:
    """Drop published_flow_input_sample table."""
    # Drop index first
    with op.batch_alter_table('published_flow_input_sample', schema=None) as batch_op:
        batch_op.drop_index('ix_published_flow_input_sample_published_flow_id')
    
    # Drop the table
    op.drop_table('published_flow_input_sample')