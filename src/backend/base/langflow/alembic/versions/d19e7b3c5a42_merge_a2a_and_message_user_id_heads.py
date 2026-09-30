"""merge a2a and message user id heads

Phase: EXPAND (no DDL - merge point only)

Revision ID: d19e7b3c5a42
Revises: 5e6d61582763, acfad963ce75
Create Date: 2026-07-13 21:15:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "d19e7b3c5a42"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("5e6d61582763", "acfad963ce75")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
