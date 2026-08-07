"""merge SSO identity and catalog policy heads

Phase: EXPAND (no DDL - merge point only)

Revision ID: f0a1b2c3d4e5
Revises: d4a7c9e1b2f6, e9f2a3b4c5d6
Create Date: 2026-08-03

Resolves the branch created when release-1.12.0 model/catalog policy
migrations landed alongside the SSO multi-identity migration that had
accidentally reused revision id e8f1a2b3c4d5.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "f0a1b2c3d4e5"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("d4a7c9e1b2f6", "e9f2a3b4c5d6")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
