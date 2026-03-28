"""Add paused to job_status_enum.

Revision ID: f7a8b9c0d1e2
Revises: 8255e9fc18d9
Create Date: 2026-03-28 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "8255e9fc18d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        # PostgreSQL: ALTER TYPE to add new enum value
        op.execute("ALTER TYPE job_status_enum ADD VALUE IF NOT EXISTS 'paused'")
    elif dialect == "sqlite":
        # SQLite stores enums as VARCHAR — no schema change needed.
        # The CHECK constraint (if any) is handled by SQLAlchemy at the application layer.
        pass
    else:
        # Other dialects: attempt the PostgreSQL path
        op.execute("ALTER TYPE job_status_enum ADD VALUE IF NOT EXISTS 'paused'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # The 'paused' value will remain in the enum but will not be used.
    pass
