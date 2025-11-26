"""Update flow_version sample_id with version_flow_input_sample references

Revision ID: 20251125000002
Revises: 20251125000001
Create Date: 2025-11-25 00:00:02.000000

This migration updates the sample_id field in flow_version table to reference
the corresponding version_flow_input_sample records.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20251125000002"
down_revision: Union[str, None] = "20251125000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update flow_version.sample_id with corresponding version_flow_input_sample.id."""
    conn = op.get_bind()

    # Update sample_id in flow_version by matching with version_flow_input_sample
    # Match on flow_version.id = version_flow_input_sample.flow_version_id
    conn.execute(text("""
        UPDATE flow_version fv
        SET sample_id = vfis.id
        FROM version_flow_input_sample vfis
        WHERE fv.id = vfis.flow_version_id
        AND fv.status_id = 5  -- Only update Published flows from migration
        AND fv.version LIKE '1.0.%'  -- Only update migrated records
    """))


def downgrade() -> None:
    """Reset sample_id to NULL for migrated records."""
    conn = op.get_bind()

    # Reset sample_id to NULL for records that were updated in this migration
    conn.execute(text("""
        UPDATE flow_version
        SET sample_id = NULL
        WHERE status_id = 5
        AND version LIKE '1.0.%'
        AND sample_id IS NOT NULL
    """))
