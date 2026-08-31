"""merge bg metrics index and sso identity heads

Phase: EXPAND (no DDL - merge point only)

Revision ID: d1c8b4e7f209
Revises: b3f7c2a91d48, c6d8e0f2a4b7
Create Date: 2026-08-31 18:20:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "d1c8b4e7f209"  # pragma: allowlist secret
down_revision: str | None = ("b3f7c2a91d48", "c6d8e0f2a4b7")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
