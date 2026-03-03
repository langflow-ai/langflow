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


def test_validator_catches_bad_expand(create_test_migration):
    """Non-nullable column + drop in EXPAND phase must be flagged."""
    content = '''\
"""
Description: Add required column and drop old one
Phase: EXPAND

Revision ID: test_bad_expand
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('users', sa.Column('email', sa.String(), nullable=False))
    op.drop_column('users', 'old_email')

def downgrade():
    pass
'''
    validator = MigrationValidator()
    result = validator.validate_migration_file(create_test_migration(content, "bad_expand.py"))

    assert not result["valid"], "Bad EXPAND should be invalid"
    violations = [v["type"] for v in result["violations"]]
    assert "BREAKING_ADD_COLUMN" in violations
    assert "IMMEDIATE_DROP" in violations


def test_validator_passes_good_expand(create_test_migration):
    """Nullable column with existence check in EXPAND phase should pass."""
    content = '''\
"""
Description: Add email_verified column
Phase: EXPAND
Safe to rollback: YES

Revision ID: test_good_expand
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
    validator = MigrationValidator()
    result = validator.validate_migration_file(create_test_migration(content, "good_expand.py"))

    assert result["valid"], f"Good EXPAND should pass but got violations: {result['violations']}"


def test_validator_catches_bad_contract(create_test_migration):
    """add_column in CONTRACT phase + missing data check must be flagged."""
    content = '''\
"""
Description: Bad contract migration
Phase: CONTRACT

Revision ID: test_bad_contract
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('users', sa.Column('new_col', sa.String(), nullable=True))
    op.drop_column('users', 'old_col')

def downgrade():
    pass
'''
    validator = MigrationValidator()
    result = validator.validate_migration_file(create_test_migration(content, "bad_contract.py"))

    assert not result["valid"], "Bad CONTRACT should be invalid"
    violations = [v["type"] for v in result["violations"]]
    assert "INVALID_PHASE_OPERATION" in violations
    assert "MISSING_DATA_CHECK" in violations


class TestExistingMigrations:
    """Validate existing migration files against the guidelines."""

    def test_legacy_migrations_flagged(self):
        """Ensure legacy migrations are flagged for missing phase markers."""
        workspace_root = Path(__file__).resolve().parents[5]
        migrations_dir = workspace_root / "src/backend/base/langflow/alembic/versions"

        validator = MigrationValidator(strict_mode=False)

        if not migrations_dir.exists():
            pytest.fail(f"Migrations directory not found at {migrations_dir}")

        legacy_migration = next(
            (f for f in migrations_dir.glob("*.py") if not f.name.startswith("00") and f.name != "__init__.py"), None
        )

        assert legacy_migration is not None, f"No legacy migration files found in {migrations_dir}"

        result = validator.validate_migration_file(legacy_migration)
        assert result["valid"] is False
        violations = [v["type"] for v in result["violations"]]
        assert "NO_PHASE_MARKER" in violations
