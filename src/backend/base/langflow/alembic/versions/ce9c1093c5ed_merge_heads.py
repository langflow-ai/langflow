"""merge heads

Revision ID: ce9c1093c5ed
Revises: b8dafef2be6b, e1705947c729
Create Date: 2026-07-08 09:10:12.149923

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = 'ce9c1093c5ed'
down_revision: Union[str, None] = ('b8dafef2be6b', 'e1705947c729')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    pass


def downgrade() -> None:
    conn = op.get_bind()
    pass
