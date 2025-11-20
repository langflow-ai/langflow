"""Sync published flow data to original flows

Revision ID: 20251120120000
Revises: 20251120000000
Create Date: 2025-11-20 12:00:00.000000

This migration syncs the flow_name and description from published_flow records
back to their original flow records (identified by flow_cloned_from).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20251120120000"
down_revision: Union[str, None] = "20251120000000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Sync published flow names and descriptions to their original flows.

    Updates flows one by one using savepoints to handle conflicts gracefully.
    Skips flows that would create duplicate names and reports them.
    """
    conn = op.get_bind()

    print("\n" + "="*80)
    print("STARTING: Sync published flow data to original flows")
    print("="*80 + "\n")

    # Fetch all published flows with their original flow info
    fetch_query = text("""
        SELECT
            pf.id as published_flow_id,
            pf.flow_name,
            pf.description,
            pf.flow_cloned_from,
            f.id as flow_id,
            f.name as current_name,
            f.description as current_description
        FROM published_flow pf
        LEFT JOIN flow f ON f.id = pf.flow_cloned_from
        WHERE pf.flow_cloned_from IS NOT NULL
        ORDER BY pf.id
    """)

    published_flows = conn.execute(fetch_query).fetchall()
    total_count = len(published_flows)

    print(f"Found {total_count} published flows to process\n")

    success_count = 0
    skip_count = 0
    conflict_count = 0
    skipped_flows = []

    for pf in published_flows:
        pub_id = pf[0]
        flow_name = pf[1]
        description = pf[2]
        flow_cloned_from = pf[3]
        flow_id = pf[4]
        current_name = pf[5]

        # Skip if original flow doesn't exist
        if not flow_id:
            print(f"⚠️  SKIP: Original flow {flow_cloned_from} not found (published_flow {pub_id})")
            skip_count += 1
            skipped_flows.append((pub_id, flow_name, "Missing original flow"))
            continue

        # Begin a nested transaction for this update
        trans = conn.begin_nested()
        try:
            # Simply update the flow with published flow name and description
            update_query = text("""
                UPDATE flow
                SET name = :flow_name,
                    description = :description
                WHERE id = :flow_id
            """)

            conn.execute(
                update_query,
                {
                    "flow_name": flow_name,
                    "description": description or "",
                    "flow_id": str(flow_cloned_from)
                }
            )

            trans.commit()
            success_count += 1
            if current_name != flow_name:
                print(f"✅ Updated flow {str(flow_id)[:8]}...: '{current_name}' → '{flow_name}'")

        except Exception as e:
            # Rollback the nested transaction
            trans.rollback()

            # Handle errors (e.g., unique constraint violations)
            error_str = str(e)
            if "unique_flow_name" in error_str or "UniqueViolation" in error_str:
                conflict_count += 1
                print(f"⚠️  CONFLICT: Flow {str(flow_id)[:8]}... - name '{flow_name}' already exists")
                skipped_flows.append((pub_id, flow_name, "Duplicate name conflict"))
            else:
                skip_count += 1
                print(f"❌ ERROR: Flow {str(flow_id)[:8]}... - {str(e)[:100]}")
                skipped_flows.append((pub_id, flow_name, f"Error: {str(e)[:50]}"))

    # Print summary
    print("\n" + "="*80)
    print("SUMMARY: Published flow data sync")
    print("="*80)
    print(f"Total processed:       {total_count}")
    print(f"✅ Successfully updated: {success_count}")
    print(f"⚠️  Name conflicts:      {conflict_count}")
    print(f"⚠️  Other skips:         {skip_count}")
    print("="*80 + "\n")

    if conflict_count > 0:
        print(f"⚠️  {conflict_count} flows skipped due to name conflicts")
        print("These flows have names that already exist in their folders.")
        print("You may need to manually rename them or resolve the conflicts.\n")

    if success_count > 0:
        print(f"🎉 Successfully synced {success_count} flows!")

    print()


def downgrade() -> None:
    """
    This is a data migration, so downgrade is a no-op.
    We cannot reliably restore the previous names and descriptions
    as they were not stored before this migration.
    """
    print("\n" + "="*80)
    print("DOWNGRADE: This is a data migration - no action taken")
    print("="*80 + "\n")
    pass
