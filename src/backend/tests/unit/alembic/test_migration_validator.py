from pathlib import Path

import pytest
from langflow.alembic.migration_validator import MigrationValidator


@pytest.fixture
def create_test_migration(tmp_path):
    def _create(content: str, filename: str) -> Path:
        p = tmp_path / filename
        p.write_text(content)
        return p

    return _create


class TestMigrationValidatorScripts:
    def test_expand_phase(self, create_test_migration):
        """Test EXPAND phase validations."""
        # Test: Good EXPAND migration
        good_expand = '''"""
Description: Add email_verified column
Phase: EXPAND
Safe to rollback: YES

Revision ID: test_expand_good
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('users')]

    if 'email_verified' not in columns:
        op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=True))

def downgrade():
    op.drop_column('users', 'email_verified')
'''

        # Test: Bad EXPAND migration
        bad_expand = '''"""
Description: Add required column
Phase: EXPAND

Revision ID: test_expand_bad
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Missing existence check and non-nullable
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False))
    # Dropping column in EXPAND phase
    op.drop_column('users', 'old_column')

def downgrade():
    pass
'''

        validator = MigrationValidator()

        # Test good migration
        good_file = create_test_migration(good_expand, "good_expand.py")
        result = validator.validate_migration_file(good_file)
        assert result["valid"], "Good EXPAND should pass"

        # Test bad migration
        bad_file = create_test_migration(bad_expand, "bad_expand.py")
        result = validator.validate_migration_file(bad_file)
        assert not result["valid"], "Bad EXPAND should fail"
        violations = [v["type"] for v in result["violations"]]
        assert len(violations) > 0

    def test_contract_phase(self, create_test_migration):
        """Test CONTRACT phase validations."""
        good_contract = '''"""
Description: Remove old column
Phase: CONTRACT

Revision ID: test_contract_good
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    bind = op.get_bind()

    # Check data migration is complete
    result = bind.execute(sa.text("""
        SELECT COUNT(*) as cnt FROM users
        WHERE old_email IS NOT NULL AND new_email IS NULL
    """)).first()

    if result.cnt > 0:
        raise Exception(f"Cannot contract: {result.cnt} rows not migrated")

    op.drop_column('users', 'old_email')

def downgrade():
    raise NotImplementedError("Cannot rollback CONTRACT phase")
'''

        validator = MigrationValidator()

        good_file = create_test_migration(good_contract, "good_contract.py")
        result = validator.validate_migration_file(good_file)
        assert result["valid"], "Good CONTRACT should pass"

    def test_phase_detection(self, create_test_migration):
        """Test phase detection from different formats."""
        test_cases = [
            ("Phase: EXPAND", "EXPAND"),
            ("phase: migrate", "MIGRATE"),
            ("PHASE: CONTRACT", "CONTRACT"),
            ("No phase marker", "UNKNOWN"),
        ]

        validator = MigrationValidator()

        for content_marker, expected_phase in test_cases:
            content = f'''"""
Migration description
{content_marker}
"""
def upgrade(): pass
def downgrade(): pass
'''
            file = create_test_migration(content, "phase_test.py")
            result = validator.validate_migration_file(file)
            detected_phase = result["phase"]
            assert detected_phase == expected_phase, f"Phase detection failed for {content_marker}"

    def test_common_mistakes(self, create_test_migration):
        """Test detection of common migration mistakes."""
        mistakes = {
            "Direct rename": """
def upgrade():
    op.rename_column('users', 'email', 'email_address')
""",
            "Direct type change": """
def upgrade():
    op.alter_column('users', 'age', type_=sa.Integer())
""",
            "Non-nullable without default": """
def upgrade():
    op.add_column('users', sa.Column('required_field', sa.String(), nullable=False))
""",
        }

        validator = MigrationValidator()

        for mistake_name, code in mistakes.items():
            content = f'''"""
Test: {mistake_name}
Phase: EXPAND
"""
from alembic import op
import sqlalchemy as sa

{code}

def downgrade(): pass
'''
            file = create_test_migration(content, f"{mistake_name}.py")
            result = validator.validate_migration_file(file)
            assert not result["valid"], f"Should detect {mistake_name}"
