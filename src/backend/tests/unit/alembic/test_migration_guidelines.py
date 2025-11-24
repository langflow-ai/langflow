import pytest
import sqlalchemy as sa
from langflow.alembic.migration_validator import MigrationValidator
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, text


# Fixture to create temporary migration files
@pytest.fixture
def create_migration_file(tmp_path):
    def _create(content):
        p = tmp_path / "test_migration.py"
        p.write_text(content)
        return p

    return _create


class TestMigrationValidator:
    """Tests for the MigrationValidator static analysis tool."""

    def test_valid_expand_migration(self, create_migration_file):
        """Test that a properly formatted EXPAND migration passes validation."""
        content = """
\"\"\"
Phase: EXPAND
\"\"\"
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Check existence for idempotency
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('users')]

    if 'new_col' not in columns:
        # Nullable=True is required for EXPAND
        op.add_column('users', sa.Column('new_col', sa.String(), nullable=True))

def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('users')]

    if 'new_col' in columns:
        # Check for data loss (warning in validation)
        op.execute("SELECT COUNT(*) FROM users WHERE new_col IS NOT NULL")
        op.drop_column('users', 'new_col')
"""
        path = create_migration_file(content)
        validator = MigrationValidator()
        result = validator.validate_migration_file(path)

        assert result["valid"] is True
        assert result["phase"] == "EXPAND"
        assert len(result["violations"]) == 0

    def test_invalid_expand_migration_breaking_change(self, create_migration_file):
        """Test that adding a non-nullable column is caught."""
        content = """
\"\"\"
Phase: EXPAND
\"\"\"
from alembic import op
import sqlalchemy as sa

def upgrade():
    # VIOLATION: nullable=False without default
    op.add_column('users', sa.Column('new_col', sa.String(), nullable=False))

def downgrade():
    op.drop_column('users', 'new_col')
"""
        path = create_migration_file(content)
        validator = MigrationValidator()
        result = validator.validate_migration_file(path)

        assert result["valid"] is False
        violations = [v["type"] for v in result["violations"]]
        assert "BREAKING_ADD_COLUMN" in violations
        # Also likely catches missing existence check
        assert "NO_EXISTENCE_CHECK" in violations

    def test_invalid_direct_rename_explicit(self, create_migration_file):
        """Test that explicit rename_column is caught."""
        content = """
\"\"\"
Phase: EXPAND
\"\"\"
from alembic import op

def upgrade():
    op.rename_column('users', 'old', 'new')

def downgrade():
    pass
"""
        path = create_migration_file(content)
        validator = MigrationValidator()
        result = validator.validate_migration_file(path)
        assert result["valid"] is False
        assert any(v["type"] == "DIRECT_RENAME" for v in result["violations"])

    def test_contract_phase_validation(self, create_migration_file):
        """Test CONTRACT phase requirements."""
        # Valid CONTRACT migration
        content = """
\"\"\"
Phase: CONTRACT
\"\"\"
from alembic import op
import sqlalchemy as sa

def upgrade():
    bind = op.get_bind()
    # DATA CHECK (Required)
    bind.execute("SELECT COUNT(*) FROM users WHERE old_col IS NOT NULL")

    op.drop_column('users', 'old_col')

def downgrade():
    # Downgrade in contract phase is hard/impossible without backup
    raise NotImplementedError("Cannot reverse CONTRACT phase")
"""
        path = create_migration_file(content)
        validator = MigrationValidator()
        result = validator.validate_migration_file(path)
        assert result["valid"] is True
        assert result["phase"] == "CONTRACT"

    def test_contract_phase_missing_data_check(self, create_migration_file):
        """Test CONTRACT phase catches missing data check."""
        content = """
\"\"\"
Phase: CONTRACT
\"\"\"
from alembic import op

def upgrade():
    # Missing data verification check
    op.drop_column('users', 'old_col')

def downgrade():
    raise NotImplementedError
"""
        path = create_migration_file(content)
        validator = MigrationValidator()
        result = validator.validate_migration_file(path)

        # NOTE: The validator currently treats this as a violation (error) despite the
        # Violation object having severity="warning" internally, because it adds it
        # to the violations list.
        violations = [v["type"] for v in result["violations"]]
        assert "MISSING_DATA_CHECK" in violations
        assert result["valid"] is False


class TestMigrationRuntimeGuidelines:
    """Tests proving that following the guidelines results in correct behavior.

    1. N-1 Compatibility (Old code works with new schema).
    2. Safe Rollback.
    """

    def test_expand_phase_compatibility_and_rollback(self):
        """Simulate an EXPAND phase migration and verify N-1 compatibility and rollback."""
        # 1. Setup Initial State (Version N-1)
        engine = create_engine("sqlite:///:memory:")
        metadata = MetaData()

        # Initial Schema
        users = Table(
            "users", metadata, Column("id", Integer, primary_key=True), Column("username", String, nullable=False)
        )
        metadata.create_all(engine)

        # Populate with some data using "Old Service"
        with engine.connect() as conn:
            conn.execute(users.insert().values(username="user_v1"))
            conn.commit()

        # 2. Apply EXPAND Migration (Version N)
        # Guideline: Add new column as nullable
        with engine.connect() as conn:
            # Verify idempotency check logic works (simulated)
            inspector = sa.inspect(conn)
            if "email" not in [c["name"] for c in inspector.get_columns("users")]:
                conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR NULL"))
                conn.commit()

        # 3. Verify N-1 Compatibility
        with engine.connect() as conn:
            # Can "Old Service" still read?
            # (Select * might get extra column, but mapped ORM usually ignores unknown unless strict)
            # Raw SQL insert from old service (doesn't know about email)
            try:
                conn.execute(text("INSERT INTO users (username) VALUES ('user_v1_after_migration')"))
                conn.commit()
            except Exception as e:
                pytest.fail(f"Old service broke after migration: {e}")

            # Can "New Service" use new features?
            conn.execute(text("INSERT INTO users (username, email) VALUES ('user_v2', 'test@example.com')"))
            conn.commit()

        # 4. Verify Rollback Safety
        # Guideline: Check for data in new column before dropping
        with engine.connect() as conn:
            # Check for data
            count = conn.execute(text("SELECT COUNT(*) FROM users WHERE email IS NOT NULL")).scalar()
            assert count is not None, "Count should not be None"
            assert count > 0, "Should have data in new column"

            # In a real scenario, we would backup here if count > 0
            # For this test, we proceed to drop, simulating the downgrade() op

            # SQLite support for DROP COLUMN
            conn.execute(text("ALTER TABLE users DROP COLUMN email"))
            conn.commit()

        # 5. Verify Post-Rollback State
        with engine.connect() as conn:
            inspector = sa.inspect(conn)
            columns = [c["name"] for c in inspector.get_columns("users")]
            assert "email" not in columns
            assert "username" in columns

            # Verify data integrity of original columns
            rows = conn.execute(text("SELECT username FROM users")).fetchall()
            usernames = [r[0] for r in rows]
            assert "user_v1" in usernames
            assert "user_v1_after_migration" in usernames
            assert "user_v2" in usernames  # This user should still exist, just lost their email
