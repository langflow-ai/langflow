"""merge_heads_job_and_memory

Revision ID: 8bb9360df775
Revises: 369268b9af8b, f6g7h8i9j0k1
Create Date: 2026-02-10 21:11:58.408118

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = '8bb9360df775'
down_revision: Union[str, None] = ('369268b9af8b', 'f6g7h8i9j0k1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
