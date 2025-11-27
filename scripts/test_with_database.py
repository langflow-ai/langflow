"""Test migrations with actual database."""

import sqlite3
import tempfile

from alembic import command
from alembic.config import Config


def test_real_migration():
    """Test migration with actual SQLite database."""
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = tmp.name

        # Create test table
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                old_email TEXT
            )
        """)
        conn.commit()

        # Create alembic.ini
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", "src/backend/base/langflow/alembic")
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

        # Run migration
        try:
            command.upgrade(alembic_cfg, "head")
            print("✅ Migration executed successfully")
        except RuntimeError as e:
            print(f"❌ Migration failed: {e}")

        # Verify schema
        cursor = conn.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Columns after migration: {columns}")

        conn.close()


if __name__ == "__main__":
    test_real_migration()
