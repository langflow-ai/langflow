"""merge_mcp_and_execution_signals_heads

Revision ID: 9d5e24d777bf
Revises: 247308ce2598, 8ce44e4858c6
Create Date: 2026-07-10 12:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "9d5e24d777bf"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("247308ce2598", "8ce44e4858c6")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
