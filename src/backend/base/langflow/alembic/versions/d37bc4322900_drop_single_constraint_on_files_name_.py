"""Drop single constraint on file.name column

Revision ID: d37bc4322900
Revises: 0882f9657f22
Create Date: 2025-09-15 11:11:37.610294

"""
import logging

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

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
        logger.info("file table does not exist, skipping")
        return
    
    db_dialect = conn.dialect.name
    logger.info(f"Running migration on {db_dialect} database")
    
    try:
        if db_dialect == "sqlite":
            # SQLite: Recreate table without single UNIQUE constraint
            logger.info("SQLite: Recreating table to remove single UNIQUE constraint on name")
            
            # Guard against schema drift: ensure expected columns before destructive rebuild
            res = conn.execute(sa.text('PRAGMA table_info("file")'))
            cols = [row[1] for row in res]
            expected = ['id', 'user_id', 'name', 'path', 'size', 'provider', 'created_at', 'updated_at']
            if set(cols) != set(expected):
                raise RuntimeError(f"SQLite: Unexpected columns on file table: {cols}. Aborting migration to avoid data loss.")

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
            op.execute("PRAGMA foreign_keys=OFF")
            try:
                op.execute("DROP TABLE file")
                op.execute("ALTER TABLE file_new RENAME TO file")
            finally:
                op.execute("PRAGMA foreign_keys=ON")
            
            logger.info("SQLite: Successfully recreated file table without single UNIQUE constraint on name")
            
        elif db_dialect == "postgresql":
            # PostgreSQL: Find and drop single-column unique constraints on 'name'
            logger.info("PostgreSQL: Finding and dropping single UNIQUE constraints and indexes on name")
            
            # Determine target schema
            schema = sa.inspect(conn).default_schema_name or "public"
            
            # Get constraint names that are single-column unique on 'name'
            result = conn.execute(sa.text("""
                SELECT conname 
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_namespace n ON t.relnamespace = n.oid
                WHERE t.relname = 'file' 
                AND n.nspname = :schema
                AND c.contype = 'u'
                AND array_length(c.conkey, 1) = 1
                AND EXISTS (
                    SELECT 1 FROM pg_attribute a
                    WHERE a.attrelid = t.oid 
                    AND a.attnum = c.conkey[1]
                    AND a.attname = 'name'
                )
            """), {"schema": schema})
            
            constraints_to_drop = [row[0] for row in result.fetchall()]
            
            if constraints_to_drop:
                for constraint_name in constraints_to_drop:
                    op.drop_constraint(constraint_name, "file", type_="unique", schema=schema)
                    logger.info(f"PostgreSQL: Dropped constraint {constraint_name}")
            else:
                logger.info("PostgreSQL: No single UNIQUE constraints found on name column")
            
            # Also drop any single-column UNIQUE indexes on name not backed by constraints
            idx_result = conn.execute(sa.text("""
                SELECT i.relname
                FROM pg_class t
                JOIN pg_namespace n ON n.oid = t.relnamespace
                JOIN pg_index ix ON ix.indrelid = t.oid
                JOIN pg_class i ON i.oid = ix.indexrelid
                WHERE t.relname = 'file'
                  AND n.nspname = :schema
                  AND ix.indisunique = TRUE
                  AND array_length(ix.indkey, 1) = 1
                  AND NOT EXISTS (SELECT 1 FROM pg_constraint c WHERE c.conindid = ix.indexrelid)
                  AND (SELECT a.attname FROM pg_attribute a 
                       WHERE a.attrelid = t.oid AND a.attnum = ix.indkey[1]) = 'name'
            """), {"schema": schema})
            for (index_name,) in idx_result.fetchall():
                op.drop_index(index_name, table_name="file", schema=schema)
                logger.info(f"PostgreSQL: Dropped unique index {index_name}")
        
        else:
            raise ValueError(f"Unsupported database dialect: {db_dialect}")
            
    except Exception as e:
        logger.error(f"Error during constraint removal: {e}")
        raise


def downgrade() -> None:
    """Add back the single unique constraint on name column."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check if file table exists
    table_names = inspector.get_table_names()
    if "file" not in table_names:
        logger.info("file table does not exist, skipping downgrade")
        return
    
    db_dialect = conn.dialect.name
    
    try:
        # Pre-check for duplicates that would violate UNIQUE(name)
        dup = conn.execute(sa.text("SELECT name FROM file GROUP BY name HAVING COUNT(*) > 1 LIMIT 1")).first()
        if dup:
            raise RuntimeError(
                "Downgrade aborted: duplicates in file.name would violate UNIQUE(name). "
                "Deduplicate before downgrading."
            )
        if db_dialect == "sqlite":
            # Add the same column validation as upgrade
            res = conn.execute(sa.text('PRAGMA table_info("file")'))
            cols = [row[1] for row in res]
            expected = ['id', 'user_id', 'name', 'path', 'size', 'provider', 'created_at', 'updated_at']
            if set(cols) != set(expected):
                raise RuntimeError(f"SQLite: Unexpected columns on file table: {cols}. Aborting downgrade.")
            # SQLite: Recreate table with both constraints
            logger.info("SQLite: Recreating table with both constraints")
            
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
            op.execute("PRAGMA foreign_keys=OFF")
            try:
                op.execute("DROP TABLE file")
                op.execute("ALTER TABLE file_new RENAME TO file")
            finally:
                op.execute("PRAGMA foreign_keys=ON")
            
            logger.info("SQLite: Restored single unique constraint on name column")
            
        elif db_dialect == "postgresql":
            # PostgreSQL: Add constraint back
            schema = sa.inspect(conn).default_schema_name or "public"
            op.create_unique_constraint("file_name_unique", "file", ["name"], schema=schema)
            logger.info("PostgreSQL: Added back single unique constraint on 'name' column")
            
        else:
            logger.info(f"Downgrade not supported for dialect: {db_dialect}")
            
    except Exception as e:
        logger.error(f"Error during downgrade: {e}")
        if "constraint" not in str(e).lower():
            raise
