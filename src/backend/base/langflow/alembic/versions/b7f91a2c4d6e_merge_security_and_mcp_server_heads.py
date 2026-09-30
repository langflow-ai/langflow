"""merge security and mcp server heads

Revision ID: b7f91a2c4d6e
Revises: 12a64232053f, 247308ce2598
Create Date: 2026-07-09 09:20:00.000000

Phase: EXPAND

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "b7f91a2c4d6e"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("12a64232053f", "247308ce2598")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
