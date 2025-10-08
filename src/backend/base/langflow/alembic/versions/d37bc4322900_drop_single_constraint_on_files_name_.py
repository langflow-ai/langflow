"""Drop single constraint on file.name column

Revision ID: d37bc4322900
Revises: 0882f9657f22
Create Date: 2025-09-15 11:11:37.610294

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = "d37bc4322900"
down_revision: Union[str, None] = "0882f9657f22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove single UNIQUE constraint on name column while preserving composite constraint."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check if file table exists
    table_names = inspector.get_table_names()
    if "file" not in table_names:
        print("file table does not exist, skipping")
        return
    
    db_dialect = conn.dialect.name
    print(f"Running migration on {db_dialect} database")
    
    try:
        if db_dialect == "sqlite":
            # SQLite: Recreate table without single UNIQUE constraint
            print("SQLite: Recreating table to remove single UNIQUE constraint on name")
            
            # Create the new table without the single UNIQUE(name) constraint
            op.execute("""
                CREATE TABLE file_new (
                    id CHAR(32) NOT NULL, 
                    user_id CHAR(32) NOT NULL, 
                    name VARCHAR NOT NULL, 
                    path VARCHAR NOT NULL, 
                    size INTEGER NOT NULL, 
                    provider VARCHAR, 
                    created_at DATETIME NOT NULL, 
                    updated_at DATETIME NOT NULL, 
                    PRIMARY KEY (id), 
                    CONSTRAINT file_name_user_id_key UNIQUE (name, user_id), 
                    FOREIGN KEY(user_id) REFERENCES user (id)
                )
            """)
            
            # Copy data from old table to new table
            op.execute("""
                INSERT INTO file_new (id, user_id, name, path, size, provider, created_at, updated_at)
                SELECT id, user_id, name, path, size, provider, created_at, updated_at
                FROM file
            """)
            
            # Drop old table and rename new table
            op.execute("DROP TABLE file")
            op.execute("ALTER TABLE file_new RENAME TO file")
            
            print("SQLite: Successfully recreated file table without single UNIQUE constraint on name")
            
        elif db_dialect == "postgresql":
            # PostgreSQL: Find and drop single-column unique constraints on 'name'
            print("PostgreSQL: Finding and dropping single UNIQUE constraint on name")
            
            # Get constraint names that are single-column unique on 'name'
            result = conn.execute(sa.text("""
                SELECT conname 
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_namespace n ON t.relnamespace = n.oid
                WHERE t.relname = 'file' 
                AND n.nspname = 'public'
                AND c.contype = 'u'
                AND array_length(c.conkey, 1) = 1
                AND EXISTS (
                    SELECT 1 FROM pg_attribute a
                    WHERE a.attrelid = t.oid 
                    AND a.attnum = c.conkey[1]
                    AND a.attname = 'name'
                )
            """))
            
            constraints_to_drop = [row[0] for row in result.fetchall()]
            
            if constraints_to_drop:
                for constraint_name in constraints_to_drop:
                    op.execute(f'ALTER TABLE "file" DROP CONSTRAINT "{constraint_name}"')
                    print(f"PostgreSQL: Dropped constraint {constraint_name}")
            else:
                print("PostgreSQL: No single UNIQUE constraints found on name column")
                
        else:
            raise ValueError(f"Unsupported database dialect: {db_dialect}")
            
    except Exception as e:
        print(f"Error during constraint removal: {e}")
        raise


def downgrade() -> None:
    """Add back the single unique constraint on name column."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check if file table exists
    table_names = inspector.get_table_names()
    if "file" not in table_names:
        print("file table does not exist, skipping downgrade")
        return
    
    db_dialect = conn.dialect.name
    
    try:
        if db_dialect == "sqlite":
            # SQLite: Recreate table with both constraints
            print("SQLite: Recreating table with both constraints")
            
            op.execute("""
                CREATE TABLE file_new (
                    id CHAR(32) NOT NULL, 
                    user_id CHAR(32) NOT NULL, 
                    name VARCHAR NOT NULL, 
                    path VARCHAR NOT NULL, 
                    size INTEGER NOT NULL, 
                    provider VARCHAR, 
                    created_at DATETIME NOT NULL, 
                    updated_at DATETIME NOT NULL, 
                    PRIMARY KEY (id), 
                    CONSTRAINT file_name_user_id_key UNIQUE (name, user_id), 
                    FOREIGN KEY(user_id) REFERENCES user (id),
                    UNIQUE (name)
                )
            """)
            
            # Copy data
            op.execute("""
                INSERT INTO file_new (id, user_id, name, path, size, provider, created_at, updated_at)
                SELECT id, user_id, name, path, size, provider, created_at, updated_at
                FROM file
            """)
            
            # Replace table
            op.execute("DROP TABLE file")
            op.execute("ALTER TABLE file_new RENAME TO file")
            
            print("SQLite: Restored single unique constraint on name column")
            
        elif db_dialect == "postgresql":
            # PostgreSQL: Add constraint back
            op.execute('ALTER TABLE "file" ADD CONSTRAINT file_name_unique UNIQUE (name)')
            print("PostgreSQL: Added back single unique constraint on 'name' column")
            
        else:
            print(f"Downgrade not supported for dialect: {db_dialect}")
            
    except Exception as e:
        print(f"Error during downgrade: {e}")
        # Don't raise in downgrade - log and continue
        pass
