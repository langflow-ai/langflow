"""merge chat history scope and span enum heads

Revision ID: 12a64232053f
Revises: b2c72e1e1439, c3e7a1b9d2f4
Create Date: 2026-07-07 17:10:41.000000

Phase: EXPAND

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "12a64232053f"  # pragma: allowlist secret
down_revision: str | None = ("b2c72e1e1439", "c3e7a1b9d2f4")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
