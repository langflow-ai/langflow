"""merge_job_asset_and_sso_heads

Revision ID: c187c3b9bb94
Revises: 26ef53e27502, b1c2d3e4f5a6
Create Date: 2026-02-25 14:19:54.858370

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = 'c187c3b9bb94'
down_revision: Union[str, None] = ('26ef53e27502', 'b1c2d3e4f5a6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    pass


def downgrade() -> None:
    conn = op.get_bind()
    pass
