"""merge_job_asset_and_sso_heads

Revision ID: c187c3b9bb94
Revises: 26ef53e27502, b1c2d3e4f5a6
Create Date: 2026-02-25 14:19:54.858370

Phase: EXPAND
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "c187c3b9bb94"
down_revision: str | Sequence[str] | None = ("26ef53e27502", "b1c2d3e4f5a6")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
