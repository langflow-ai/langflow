"""merge published_flow and file constraints

Revision ID: 99999999999
Revises: 20251024120000, d37bc4322900
Create Date: 2025-10-26 04:20:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "99999999999"
down_revision: Union[str, Sequence[str], None] = ("20251024120000", "d37bc4322900")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration - no operations needed."""
    pass


def downgrade() -> None:
    """Merge migration - no operations needed."""
    pass