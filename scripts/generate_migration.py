"""Generate Expand-Contract pattern compliant Alembic migrations."""

import hashlib  # noqa: F401
import random  # noqa: F401
import re  # noqa: F401
import subprocess  # noqa: F401
from datetime import datetime  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Optional  # noqa: F401

import click  # noqa: F401

TEMPLATES = {
    "expand": '''"""
{description}
Phase: EXPAND
Safe to rollback: YES
Services compatible: All versions
Next phase: MIGRATE after all services deployed

Revision ID: {revision}
Revises: {down_revision}
Create Date: {create_date}
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect

# revision identifiers, used by Alembic
revision = '{revision}'
down_revision = {down_revision}
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    EXPAND PHASE: Add new schema elements (backward compatible)
    - All new columns must be nullable or have defaults
    - No breaking changes to existing schema
    - Services using old schema continue to work
    """
    bind = op.get_bind()
    inspector = inspect(bind)

    # Get existing columns for idempotency
        columns = [col['name'] for col in inspector.get_columns('{table_name}')]
    }

    # Add new nullable column (always check existence first)
    if '{column_name}' not in columns:
        op.add_column('{table_name}',
            sa.Column('{column_name}', sa.{column_type}(), nullable=True{default_value})
        )

        print(f"✅ Added column '{column_name}' to table '{table_name}'")

        # Optional: Add index for performance
        # op.create_index('ix_{table_name}_{column_name}', '{table_name}', ['{column_name}'])
    else:
        print(f"⏭️  Column '{column_name}' already exists in table '{table_name}'")

    # Verify the change
    result = bind.execute(text(
        "SELECT COUNT(*) as cnt FROM {table_name}"
    )).first()
    print(f"📊 EXPAND phase complete for {{result.cnt}} rows in {table_name}")


def downgrade() -> None:
    """
    Rollback EXPAND phase
    - Safe to rollback as it only removes additions
    - Check for data loss before dropping
    """
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('{table_name}')]

    if '{column_name}' in columns:
        # Check if column has data
        result = bind.execute(text("""
            SELECT COUNT(*) as cnt FROM {table_name}
            WHERE {column_name} IS NOT NULL
        """)).first()

        if result and result.cnt > 0:
            print(f"⚠️  Warning: Dropping column '{column_name}' with {{result.cnt}} non-null values")

            # Optional: Create backup table
            backup_table = '_{table_name}_{column_name}_backup_' + datetime.now().strftime('%Y%m%d_%H%M%S')
            bind.execute(text(f"""
                CREATE TABLE {{backup_table}} AS
                SELECT id, {column_name}, NOW() as backed_up_at
                FROM {table_name}
                WHERE {column_name} IS NOT NULL
            """))
            print(f"💾 Created backup table: {{backup_table}}")

        op.drop_column('{table_name}', '{column_name}')
        print(f"✅ Dropped column '{column_name}' from table '{table_name}'")
    else:
        print(f"⏭️  Column '{column_name}' doesn't exist in table '{table_name}'")
''',
    "migrate": '''"""
{description}
Phase: MIGRATE
Safe to rollback: PARTIAL (data migration may be lost)
Services compatible: Both old and new versions
Next phase: CONTRACT after 30+ days and full adoption

Revision ID: {revision}
Revises: {down_revision}
Create Date: {create_date}
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from datetime import datetime

# revision identifiers, used by Alembic
revision = '{revision}'
down_revision = {down_revision}
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    MIGRATE PHASE: Transition data to new schema
    - Backfill data from old columns to new
    - Both old and new columns coexist
    - Services can use either column
    """
    bind = op.get_bind()

    print("🔄 Starting data migration...")

    # Backfill data from old column to new (if applicable)
    {migration_logic}

    # Report migration progress
    result = bind.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE {new_column} IS NOT NULL) as migrated,
            COUNT(*) FILTER (WHERE {new_column} IS NULL) as not_migrated,
            COUNT(*) as total
        FROM {table_name}
    """)).first()

    print(f"📊 Migration Statistics:")
    print(f"  - Total rows: {{result.total}}")
    print(f"  - Migrated: {{result.migrated}} ({{result.migrated * 100 / result.total if result.total > 0 else 0:.1f}}%)")
    print(f"  - Not migrated: {{result.not_migrated}}")

    if result.not_migrated > 0:
        print(f"⚠️  WARNING: {{result.not_migrated}} rows not yet migrated")
        print(f"   Consider running a background job to complete migration")
    else:
        print(f"✅ All rows successfully migrated")

    # Log migration completion
    bind.execute(text("""
        INSERT INTO alembic_version_history (version_num, phase, completed_at)
        VALUES (:version, 'MIGRATE', :timestamp)
        ON CONFLICT (version_num) DO UPDATE
        SET phase = 'MIGRATE', completed_at = :timestamp
    """), {{"version": revision, "timestamp": datetime.now()}})


def downgrade() -> None:
    """
    Rollback MIGRATE phase
    - Usually no action needed
    - Data remains in both old and new columns
    """
    print("⚠️  MIGRATE phase rollback - data remains in both columns")
    print("   Services can continue using either old or new schema")

    # Optional: Log rollback
    bind = op.get_bind()
    bind.execute(text("""
        UPDATE alembic_version_history
        SET phase = 'MIGRATE_ROLLED_BACK', completed_at = NOW()
        WHERE version_num = :version
    """), {{"version": revision}})
''',  # noqa: E501
    "contract": '''"""
{description}
Phase: CONTRACT
Safe to rollback: NO (old schema removed)
Services compatible: New versions only
Prerequisites: All services using new schema for 30+ days

Revision ID: {revision}
Revises: {down_revision}
Create Date: {create_date}
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect
from datetime import datetime, timedelta

# revision identifiers, used by Alembic
revision = '{revision}'
down_revision = {down_revision}
branch_labels = None
depends_on = None

# Configuration
MIN_MIGRATION_DAYS = 30  # Minimum days before contracting


def upgrade() -> None:
    """
    CONTRACT PHASE: Remove old schema elements
    - Verify all services have migrated
    - Ensure data migration is complete
    - Remove deprecated columns/tables
    - Make new columns non-nullable if needed
    """
    bind = op.get_bind()
    inspector = inspect(bind)

    print("🔍 Verifying migration readiness...")

    # Check 1: Verify migration completion
    {verification_checks}

    # Check 2: Verify no recent usage of old column (if monitoring is set up)
    try:
        result = bind.execute(text("""
            SELECT MAX(last_accessed) as last_use
            FROM column_usage_stats
            WHERE table_name = '{table_name}'
            AND column_name = '{old_column}'
        """)).first()

        if result and result.last_use:
            days_since_use = (datetime.now() - result.last_use).days
            if days_since_use < MIN_MIGRATION_DAYS:
                raise Exception(
                    f"❌ Cannot contract: old column used {{days_since_use}} days ago "
                    f"(minimum: {{MIN_MIGRATION_DAYS}} days)"
                )
            print(f"✅ Old column last used {{days_since_use}} days ago")
    except Exception as e:
        if "column_usage_stats" not in str(e):
            raise
        print("⏭️  No usage tracking table found, skipping usage check")

    # Check 3: Create final backup before removing
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = 'backup_{table_name}_{old_column}_' + timestamp

    print(f"💾 Creating final backup: {{backup_table}}")
    bind.execute(text(f"""
        CREATE TABLE {{backup_table}} AS
        SELECT * FROM {table_name}
        WHERE {old_column} IS NOT NULL
        LIMIT 10000  -- Limit backup size
    """))

    # Remove old column
    columns = [col['name'] for col in inspector.get_columns('{table_name}')]
''',
}
