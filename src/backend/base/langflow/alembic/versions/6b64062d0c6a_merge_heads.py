"""Merge heads

Revision ID: 6b64062d0c6a
Revises: a1b2c3d4e5f6, b1c2d3e4f5a6
Create Date: 2026-02-25 11:47:16.136706

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6b64062d0c6a"
down_revision: str | None = ("a1b2c3d4e5f6", "b1c2d3e4f5a6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()


def downgrade() -> None:
    conn = op.get_bind()
