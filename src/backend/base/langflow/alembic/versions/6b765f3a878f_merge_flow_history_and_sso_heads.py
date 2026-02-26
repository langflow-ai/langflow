"""merge flow_history and sso heads

Revision ID: 6b765f3a878f
Revises: 7d327cfafab6, b1c2d3e4f5a6
Create Date: 2026-02-26 09:40:02.541589

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6b765f3a878f"
down_revision: str | None = ("7d327cfafab6", "b1c2d3e4f5a6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()


def downgrade() -> None:
    conn = op.get_bind()
