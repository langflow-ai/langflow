"""merge release branch heads

Revision ID: 690d24733555
Revises: 439697865628, c9f2e5a7b1d4
Create Date: 2026-09-09 10:06:44.670577

Phase: EXPAND
Safe to rollback: YES (no DDL at all).

Merging release-1.13.0 into this branch left the revision graph with more than
one head, and alembic refuses to resolve ``head`` while that is true — the
backend aborts at startup with "Multiple head revisions are present". This
revision only rejoins the branches; it changes no schema.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "690d24733555"  # pragma: allowlist secret
down_revision: tuple[str, ...] = ("439697865628", "c9f2e5a7b1d4")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No schema change: this revision exists only to rejoin two heads."""


def downgrade() -> None:
    """No schema change to undo."""
