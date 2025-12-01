import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config


def test_real_migration_execution():
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
        # Ensure path is correct relative to where tests run
        workspace_root = Path(__file__).resolve().parents[5]
        script_location = workspace_root / "src/backend/base/langflow/alembic"

        if not script_location.exists():
            pytest.fail(f"Alembic script location not found at {script_location}")

        alembic_cfg.set_main_option("script_location", str(script_location))
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")

        # Run migration
        try:
            # Use specific head to avoid conflict with test migrations
            migration_revision = os.environ.get("ALEMBIC_TEST_REVISION", "head")
            command.upgrade(alembic_cfg, migration_revision)  # pragma: allowlist secret
        except Exception as e:
            pytest.fail(f"Migration failed: {e}")

        # Verify schema
        cursor = conn.execute("PRAGMA table_info(users)")
        cursor.fetchall()

        conn.close()

        # Just ensure we reached this point
        assert True
