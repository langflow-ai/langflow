"""Update flow_version user information from flow and user tables

Revision ID: 20251125000003
Revises: 20251125000002
Create Date: 2025-11-25 00:00:03.000000

This migration updates user-related fields in flow_version table by joining
with flow and user tables to get accurate user information.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20251125000003"
down_revision: Union[str, None] = "20251125000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update flow_version user fields with data from flow and user tables."""
    conn = op.get_bind()

    # Update user-related fields in flow_version by joining with flow and user tables
    conn.execute(text("""
        UPDATE flow_version fv
        SET
            submitted_by = u.id,
            submitted_by_name = INITCAP(REPLACE(SPLIT_PART(u.username, '@', 1), '.', ' ')),
            submitted_by_email = u.username,
            published_by = u.id,
            published_by_name = INITCAP(REPLACE(SPLIT_PART(u.username, '@', 1), '.', ' ')),
            published_by_email = u.username
        FROM flow f
        INNER JOIN "user" u ON f.user_id = u.id
        WHERE fv.original_flow_id = f.id
    """))


def downgrade() -> None:
    """Reset user fields to NULL for all updated records."""
    conn = op.get_bind()

    # This is a data-only migration, downgrade would set fields back to NULL
    # However, since we're updating existing data without filters,
    # we cannot reliably restore previous values
    # Keeping this as a placeholder - in practice, this migration should not be downgraded
    pass