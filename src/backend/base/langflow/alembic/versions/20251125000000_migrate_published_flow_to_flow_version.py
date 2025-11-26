"""Migrate published_flow to flow_version

Revision ID: 20251125000000
Revises: 20251121000000
Create Date: 2025-11-25 00:00:00.000000

This migration copies data from published_flow to flow_version.
For each published flow, we create a corresponding flow_version record with Published status.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20251125000000"
down_revision: Union[str, None] = "20251121000000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate published_flow data to flow_version."""
    conn = op.get_bind()

    # Insert data from published_flow into flow_version
    # Use ROW_NUMBER to assign unique version numbers (1.0.0, 1.0.1, 1.0.2, etc.) per original flow
    # Extract name from email: "jagveer@autonomize.ai" -> "Jagveer", "sourabh.rai@autonomize.ai" -> "Sourabh Rai"
    conn.execute(text("""
        WITH numbered_flows AS (
            SELECT
                pf.*,
                ROW_NUMBER() OVER (
                    PARTITION BY pf.flow_cloned_from
                    ORDER BY pf.created_at
                ) - 1 as version_number
            FROM published_flow pf
            WHERE pf.flow_cloned_from IS NOT NULL
        )
        INSERT INTO flow_version (
            id,
            original_flow_id,
            version_flow_id,
            status_id,
            version,
            title,
            description,
            tags,
            agent_logo,
            sample_id,
            submitted_by,
            submitted_by_name,
            submitted_by_email,
            submitted_at,
            reviewed_by,
            reviewed_by_name,
            reviewed_by_email,
            reviewed_at,
            rejection_reason,
            published_by,
            published_by_name,
            published_by_email,
            published_at,
            created_at,
            updated_at
        )
        SELECT
            pf.id,                                      -- Use published_flow.id as flow_version.id
            pf.flow_cloned_from,                        -- original_flow_id
            pf.flow_id,                                 -- version_flow_id
            5,                                          -- status_id = 5 (Published)
            CONCAT('1.0.', pf.version_number),          -- version: 1.0.0, 1.0.1, 1.0.2, etc.
            pf.flow_name,                               -- title
            pf.description,                             -- description
            pf.tags,                                    -- tags
            pf.flow_icon,                               -- agent_logo
            NULL,                                       -- sample_id (will be set later)
            pf.published_by,                            -- submitted_by
            -- Extract name from email: replace dots with spaces and title case
            INITCAP(REPLACE(SPLIT_PART(pf.published_by_username, '@', 1), '.', ' ')),  -- submitted_by_name
            pf.published_by_username,                   -- submitted_by_email
            pf.created_at,                              -- submitted_at
            pf.published_by,                            -- reviewed_by
            'Rishi kumar',                              -- reviewed_by_name (hardcoded)
            'rishikant.kumar@autonomize.ai',            -- reviewed_by_email (hardcoded)
            pf.updated_at,                              -- reviewed_at
            NULL,                                       -- rejection_reason
            pf.published_by,                            -- published_by
            -- Extract name from email: replace dots with spaces and title case
            INITCAP(REPLACE(SPLIT_PART(pf.published_by_username, '@', 1), '.', ' ')),  -- published_by_name
            pf.published_by_username,                   -- published_by_email
            pf.updated_at,                              -- published_at
            pf.created_at,                              -- created_at
            pf.updated_at                               -- updated_at
        FROM numbered_flows pf
    """))


def downgrade() -> None:
    """Remove migrated data from flow_version."""
    conn = op.get_bind()

    # Delete records that were migrated from published_flow
    # We identify them by status_id = 5 (Published) and version starting with '1.0.'
    conn.execute(text("""
        DELETE FROM flow_version
        WHERE status_id = 5
        AND version LIKE '1.0.%'
        AND id IN (
            SELECT id FROM published_flow
        )
    """))
