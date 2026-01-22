"""Merge migration branches

Revision ID: 4bf7a42c9ae6
Revises: 182e5471b900
Create Date: 2026-01-22 10:12:21.819665

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = '4bf7a42c9ae6'
down_revision: Union[str, None] = '182e5471b900'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    pass


def downgrade() -> None:
    conn = op.get_bind()
    pass
