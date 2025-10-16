"""Merge component mapping and file constraint branches

Revision ID: 5a47aaed1f05
Revises: a1b2c3d4e5f6, d37bc4322900
Create Date: 2025-10-16 12:51:02.212731

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = '5a47aaed1f05'
down_revision: Union[str, None] = ('a1b2c3d4e5f6', 'd37bc4322900')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    pass


def downgrade() -> None:
    conn = op.get_bind()
    pass
