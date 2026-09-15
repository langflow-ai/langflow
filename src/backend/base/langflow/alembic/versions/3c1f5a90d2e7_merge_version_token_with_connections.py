"""merge flow version token with the connections heads

Revision ID: 3c1f5a90d2e7
Revises: 9b6b6666bd71, a7d8e9f0b1c2
Create Date: 2026-09-14 19:05:11.402118

Phase: EXPAND
Safe to rollback: YES (no DDL at all).

The release branch added the connection tables while this branch carried the
flow version token, so the two lines are independent heads again. Alembic
refuses to resolve ``head`` while more than one exists and the backend aborts at
startup with "Multiple head revisions are present", which is what CI hit. This
revision only rejoins them; it changes no schema.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "3c1f5a90d2e7"  # pragma: allowlist secret
down_revision: tuple[str, ...] = ("9b6b6666bd71", "a7d8e9f0b1c2")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No schema change: this revision exists only to rejoin two heads."""


def downgrade() -> None:
    """No schema change to undo."""
