"""merge security and release 1.11 heads

Revision ID: 0819aa415ead
Revises: 9d5e24d777bf, b7f91a2c4d6e
Create Date: 2026-07-13 16:00:00.000000

Phase: EXPAND

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0819aa415ead"  # pragma: allowlist secret
down_revision: str | None = ("9d5e24d777bf", "b7f91a2c4d6e")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
