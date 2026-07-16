"""merge a2a tasks timestamps and hitl heads

Phase: EXPAND (no DDL - merge point only)

Revision ID: acfad963ce75
Revises: 9cbe2f682e12, c4e9a1b7d2f6
Create Date: 2026-07-13 11:55:19.505336

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "acfad963ce75"  # pragma: allowlist secret
down_revision: str | None = ("9cbe2f682e12", "c4e9a1b7d2f6")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
