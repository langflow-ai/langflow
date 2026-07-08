"""merge alembic heads

Revision ID: 844cad9a53fa
Revises: 4f0d2c9a8b7e, e1705947c729
Create Date: 2026-07-07 18:21:12.797551

Phase: EXPAND

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "844cad9a53fa"
down_revision: str | None = ("4f0d2c9a8b7e", "e1705947c729")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
