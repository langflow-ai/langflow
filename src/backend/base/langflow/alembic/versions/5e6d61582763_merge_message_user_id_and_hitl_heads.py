"""merge message user id and hitl heads

Revision ID: 5e6d61582763
Revises: 47aca8c17d23, 9cbe2f682e12
Create Date: 2026-07-13 17:00:00.000000

Phase: EXPAND

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "5e6d61582763"  # pragma: allowlist secret
down_revision: str | None = ("47aca8c17d23", "9cbe2f682e12")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
