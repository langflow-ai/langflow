"""update access_type case to uppercase

Revision ID: update_access_type_case
Revises: f3b2d1f1002d
Create Date: 2024-03-18 22:33:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'update_access_type_case'
down_revision: Union[str, None] = 'f3b2d1f1002d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Update lowercase 'private' to uppercase 'PRIVATE'
    op.execute("UPDATE flow SET access_type = 'PRIVATE' WHERE access_type = 'private'")
    # Update lowercase 'public' to uppercase 'PUBLIC'
    op.execute("UPDATE flow SET access_type = 'PUBLIC' WHERE access_type = 'public'")

def downgrade() -> None:
    # Update uppercase 'PRIVATE' to lowercase 'private'
    op.execute("UPDATE flow SET access_type = 'private' WHERE access_type = 'PRIVATE'")
    # Update uppercase 'PUBLIC' to lowercase 'public'
    op.execute("UPDATE flow SET access_type = 'public' WHERE access_type = 'PUBLIC'") 