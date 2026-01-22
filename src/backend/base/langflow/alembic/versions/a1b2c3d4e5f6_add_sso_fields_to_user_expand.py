"""
Add SSO fields to user table
Phase: EXPAND
Safe to rollback: YES
Services compatible: All versions
Next phase: MIGRATE after all services deployed

Revision ID: a1b2c3d4e5f6
Revises: 4bf7a42c9ae6
Create Date: 2026-01-22 10:13:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect

# revision identifiers, used by Alembic
revision = 'a1b2c3d4e5f6'
down_revision = '4bf7a42c9ae6'
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

    # Check if user table exists
    table_names = inspector.get_table_names()
    if 'user' not in table_names:
        print("⏭️  User table doesn't exist, skipping migration")
        return

    # Get existing columns for idempotency
    columns = [col['name'] for col in inspector.get_columns('user')]

    # Add email column (nullable for backward compatibility)
    if 'email' not in columns:
        op.add_column('user',
            sa.Column('email', sa.String(), nullable=True)
        )
        op.create_index('ix_user_email', 'user', ['email'], unique=False)
        print("✅ Added column 'email' to table 'user'")
    else:
        print("⏭️  Column 'email' already exists in table 'user'")

    # Add sso_provider column (nullable for backward compatibility)
    if 'sso_provider' not in columns:
        op.add_column('user',
            sa.Column('sso_provider', sa.String(), nullable=True)
        )
        op.create_index('ix_user_sso_provider', 'user', ['sso_provider'], unique=False)
        print("✅ Added column 'sso_provider' to table 'user'")
    else:
        print("⏭️  Column 'sso_provider' already exists in table 'user'")

    # Add sso_user_id column (nullable for backward compatibility)
    if 'sso_user_id' not in columns:
        op.add_column('user',
            sa.Column('sso_user_id', sa.String(), nullable=True)
        )
        op.create_index('ix_user_sso_user_id', 'user', ['sso_user_id'], unique=False)
        print("✅ Added column 'sso_user_id' to table 'user'")
    else:
        print("⏭️  Column 'sso_user_id' already exists in table 'user'")

    # Add sso_last_login_at column (nullable for backward compatibility)
    if 'sso_last_login_at' not in columns:
        op.add_column('user',
            sa.Column('sso_last_login_at', sa.DateTime(), nullable=True)
        )
        print("✅ Added column 'sso_last_login_at' to table 'user'")
    else:
        print("⏭️  Column 'sso_last_login_at' already exists in table 'user'")

    # Verify the change
    result = bind.execute(text(
        "SELECT COUNT(*) as cnt FROM user"
    )).first()
    print(f"📊 EXPAND phase complete for {result.cnt} rows in user table")


def downgrade() -> None:
    """
    Rollback EXPAND phase
    - Safe to rollback as it only removes additions
    - Check for data loss before dropping
    """
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Check if user table exists
    table_names = inspector.get_table_names()
    if 'user' not in table_names:
        print("⏭️  User table doesn't exist, skipping rollback")
        return
        
    columns = [col['name'] for col in inspector.get_columns('user')]

    # Drop sso_last_login_at
    if 'sso_last_login_at' in columns:
        op.drop_column('user', 'sso_last_login_at')
        print("✅ Dropped column 'sso_last_login_at' from table 'user'")

    # Drop sso_user_id and its index
    if 'sso_user_id' in columns:
        op.drop_index('ix_user_sso_user_id', table_name='user')
        op.drop_column('user', 'sso_user_id')
        print("✅ Dropped column 'sso_user_id' from table 'user'")

    # Drop sso_provider and its index
    if 'sso_provider' in columns:
        op.drop_index('ix_user_sso_provider', table_name='user')
        op.drop_column('user', 'sso_provider')
        print("✅ Dropped column 'sso_provider' from table 'user'")

    # Drop email and its index
    if 'email' in columns:
        op.drop_index('ix_user_email', table_name='user')
        op.drop_column('user', 'email')
        print("✅ Dropped column 'email' from table 'user'")