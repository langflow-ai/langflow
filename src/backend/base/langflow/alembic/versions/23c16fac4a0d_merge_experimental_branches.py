"""merge_experimental_branches

Revision ID: 23c16fac4a0d
Revises: 3671f35245e5, 369268b9af8b, bcbbf8c17c25
Create Date: 2026-02-03 23:52:53.170655

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = '23c16fac4a0d'
down_revision: Union[str, None] = ('3671f35245e5', '369268b9af8b', 'bcbbf8c17c25')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    pass


def downgrade() -> None:
    conn = op.get_bind()
    pass
