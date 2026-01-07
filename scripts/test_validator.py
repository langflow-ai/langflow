"""Test script for migration validator."""

import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.backend.base.langflow.alembic.migration_validator import MigrationValidator


def create_test_migration(content: str, filename: str) -> Path:
    """Create a temporary migration file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=filename, delete=False) as f:
        f.write(content)
        return Path(f.name)


def test_expand_phase():
    """Test EXPAND phase validations."""
    print("\n🧪 Testing EXPAND Phase Validations...")

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
    print(f"  ✅ Good EXPAND: Valid={result['valid']} (expected: True)")
    assert result["valid"], "Good EXPAND should pass"  # noqa: S101
    os.unlink(good_file)  # noqa: PTH108

    # Test bad migration
    bad_file = create_test_migration(bad_expand, "bad_expand.py")
    result = validator.validate_migration_file(bad_file)
    print(f"  ✅ Bad EXPAND: Valid={result['valid']} (expected: False)")
    print(f"     Violations: {len(result['violations'])}")
    for v in result["violations"]:
        print(f"     - {v['type']}: {v['message']}")
    assert not result["valid"], "Bad EXPAND should fail"  # noqa: S101
    os.unlink(bad_file)  # noqa: PTH108


def test_contract_phase():
    """Test CONTRACT phase validations."""
    print("\n🧪 Testing CONTRACT Phase Validations...")

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
    print(f"  ✅ Good CONTRACT: Valid={result['valid']} (expected: True)")
    os.unlink(good_file)  # noqa: PTH108


def test_phase_detection():
    """Test phase detection from different formats."""
    print("\n🧪 Testing Phase Detection...")

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
        print(f"  ✅ '{content_marker}' → {detected_phase} (expected: {expected_phase})")
        assert detected_phase == expected_phase, f"Phase detection failed for {content_marker}"  # noqa: S101
        os.unlink(file)  # noqa: PTH108


def test_common_mistakes():
    """Test detection of common migration mistakes."""
    print("\n🧪 Testing Common Mistake Detection...")

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
        print(f"  ✅ {mistake_name}: Detected={not result['valid']}")
        assert not result["valid"], f"Should detect {mistake_name}"  # noqa: S101
        os.unlink(file)  # noqa: PTH108


def main():
    print("=" * 60)
    print("🚀 Migration Validator Test Suite")
    print("=" * 60)

    try:
        test_expand_phase()
        test_contract_phase()
        test_phase_detection()
        test_common_mistakes()

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except (OSError, ImportError) as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
