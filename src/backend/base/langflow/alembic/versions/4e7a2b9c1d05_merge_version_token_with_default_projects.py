"""merge flow version token with the personal default projects head

Revision ID: 4e7a2b9c1d05
Revises: 3c1f5a90d2e7, d8f2c3a4b5e6
Create Date: 2026-09-28 12:00:00.000000

Phase: EXPAND
Safe to rollback: YES (no DDL at all).

The release branch marked personal default projects while this branch carried
the flow version token, so the two lines are independent heads again. Alembic
refuses to resolve ``head`` while more than one exists and the backend aborts at
startup with "Multiple head revisions are present". This revision only rejoins
them; it changes no schema.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "4e7a2b9c1d05"  # pragma: allowlist secret
down_revision: tuple[str, ...] = ("3c1f5a90d2e7", "d8f2c3a4b5e6")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No schema change: this revision exists only to rejoin two heads."""


def downgrade() -> None:
    """No schema change to undo."""
