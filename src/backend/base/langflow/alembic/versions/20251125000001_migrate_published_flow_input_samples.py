"""Migrate published_flow_input_sample to version_flow_input_sample

Revision ID: 20251125000001
Revises: 20251121000000
Create Date: 2025-11-25 00:00:01.000000

This migration copies data from published_flow_input_sample to version_flow_input_sample.
For each published flow input sample, we create a corresponding version input sample record.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20251125000001"
down_revision: Union[str, None] = "20251125000000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate published_flow_input_sample data to version_flow_input_sample."""
    conn = op.get_bind()

    # Insert data from published_flow_input_sample into version_flow_input_sample
    # Join with published_flow to get the original flow_id (flow_cloned_from)
    conn.execute(text("""
        INSERT INTO version_flow_input_sample (
            id,
            flow_version_id,
            original_flow_id,
            version,
            storage_account,
            container_name,
            file_names,
            sample_text,
            sample_output,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),              -- Generate new UUID for id
            input.published_flow_id,        -- flow_version_id from published_flow_input_sample
            pf.flow_cloned_from,            -- original_flow_id from published_flow
            '1.0.0',                        -- Default version for migrated data
            input.storage_account,          -- storage_account from published_flow_input_sample
            input.container_name,           -- container_name from published_flow_input_sample
            input.file_names,               -- file_names from published_flow_input_sample
            input.sample_text,              -- sample_text from published_flow_input_sample
            input.sample_output,            -- sample_output from published_flow_input_sample
            NOW(),                          -- created_at
            NOW()                           -- updated_at
        FROM published_flow_input_sample input
        INNER JOIN published_flow pf ON input.published_flow_id = pf.id
        WHERE pf.flow_cloned_from IS NOT NULL  -- Only migrate if we have an original flow reference
    """))


def downgrade() -> None:
    """Remove migrated data from version_flow_input_sample."""
    conn = op.get_bind()

    # Delete records that were migrated from published_flow_input_sample
    # We identify them by version starting with '1.0.' and flow_version_id matching published_flow.id
    conn.execute(text("""
        DELETE FROM version_flow_input_sample
        WHERE version LIKE '1.0.%'
        AND flow_version_id IN (
            SELECT id FROM published_flow
        )
    """))
