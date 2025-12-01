"""Remove Approved status and migrate to Published

Revision ID: 20251128000001
Revises: 20251125000003
Create Date: 2025-11-28 00:00:01.000000

This migration:
1. Updates status from Approved (3) to Published (5) in flow_version table
2. Deletes Approved status from flow_status table
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20251128000001"
down_revision: Union[str, None] = "20251125000003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove Approved status and migrate to Published."""
    conn = op.get_bind()

    # Step 1: Update status from Approved (3) to Published (5) in flow_version
    print("Updating flow_version: Approved (3) → Published (5)...")
    result = conn.execute(text("""
        UPDATE flow_version
        SET status_id = 5
        WHERE status_id = 3
    """))
    print(f"Updated {result.rowcount} flow_version records")

    # Step 2: Delete Approved status from flow_status table
    print("Deleting Approved status from flow_status...")
    result = conn.execute(text("""
        DELETE FROM flow_status
        WHERE id = 3 AND status_name = 'Approved'
    """))
    print(f"Deleted {result.rowcount} flow_status records")

    print("Migration completed successfully!")


def downgrade() -> None:
    """Restore Approved status."""
    conn = op.get_bind()

    # Step 1: Re-create Approved status
    print("Re-creating Approved status...")
    conn.execute(text("""
        INSERT INTO flow_status (id, status_name)
        VALUES (3, 'Approved')
    """))

    # Step 2: Revert Published (5) back to Approved (3) for records that were migrated
    # Note: We cannot distinguish which records were originally Approved vs originally Published
    # This is a best-effort downgrade
    print("Reverting Published back to Approved...")
    # Do not revert - too risky to change existing Published records
    print("Downgrade completed - Approved status recreated but records not reverted")
