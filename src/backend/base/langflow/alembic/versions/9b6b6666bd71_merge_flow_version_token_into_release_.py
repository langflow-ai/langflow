"""merge flow version token into release heads

Revision ID: 9b6b6666bd71
Revises: 439697865628, e8f0a2c4d6b9
Create Date: 2026-09-10 09:12:44.180312

Phase: EXPAND
Safe to rollback: YES (no DDL at all).

The flow version-token migration and the release branch's own merge revision are
two independent heads, and alembic refuses to resolve ``head`` while more than
one exists — the backend aborts at startup with "Multiple head revisions are
present". This revision only rejoins them; it changes no schema.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "9b6b6666bd71"  # pragma: allowlist secret
down_revision: tuple[str, ...] = ("439697865628", "e8f0a2c4d6b9")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No schema change: this revision exists only to rejoin two heads."""


def downgrade() -> None:
    """No schema change to undo."""
