"""Rename default folder

Revision ID: d9a6ea21edcd
Revises: 66f72f04a1de
Create Date: 2025-07-02 09:42:46.891585

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9a6ea21edcd"
down_revision: str | None = "66f72f04a1de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check if the folder table exists
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()

    if "folder" not in table_names:
        # If folder table doesn't exist, skip this migration
        return

    # Rename "My Projects" to "Starter Project" only for users who don't already have a "Starter Project" folder
    # This prevents unique constraint violations
    update_query = sa.text("""
        UPDATE folder
        SET name = 'Starter Project'
        WHERE name = 'My Projects'
        AND NOT EXISTS (
            SELECT 1 FROM folder f2
            WHERE f2.user_id = folder.user_id
            AND f2.name = 'Starter Project'
        )
    """)

    conn.execute(update_query)


def downgrade() -> None:
    conn = op.get_bind()

    # Check if the folder table exists
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()

    if "folder" not in table_names:
        # If folder table doesn't exist, skip this migration
        return

    # Rename "Starter Project" back to "My Projects" only for users who don't already have a "My Projects" folder
    # This prevents unique constraint violations
    update_query = sa.text("""
        UPDATE folder
        SET name = 'My Projects'
        WHERE name = 'Starter Project'
        AND NOT EXISTS (
            SELECT 1 FROM folder f2
            WHERE f2.user_id = folder.user_id
            AND f2.name = 'My Projects'
        )
    """)

    conn.execute(update_query)
