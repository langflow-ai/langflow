from pathlib import Path

import pytest
from langflow.alembic.migration_validator import MigrationValidator


class TestExistingMigrations:
    """Validate all existing migration files against the guidelines."""

    def test_validation_of_test_migrations(self):
        """Verify specific test migrations (001, 002, 003) are identified correctly.

        They should be identified as valid or invalid by the validator.
        """
        workspace_root = Path(__file__).resolve().parents[5]
        migrations_dir = workspace_root / "src/backend/base/langflow/alembic/versions"

        if not migrations_dir.exists():
            pytest.fail(f"Migrations directory not found at {migrations_dir}")

        validator = MigrationValidator(strict_mode=False)

        # 1. Test Good Expansion
        good_expand = migrations_dir / "002_good_expand0.py"
        if good_expand.exists():
            result = validator.validate_migration_file(good_expand)
            assert result["valid"] is True, f"002_good_expand0.py should be valid but got: {result['violations']}"

        # 2. Test Bad Expansion
        bad_expand = migrations_dir / "001_bad_expand0.py"
        if bad_expand.exists():
            result = validator.validate_migration_file(bad_expand)
            assert result["valid"] is False, "001_bad_expand0.py should be invalid"
            violations = [v["type"] for v in result["violations"]]
            assert "BREAKING_ADD_COLUMN" in violations
            assert "IMMEDIATE_DROP" in violations

        # 3. Test Bad Contract
        bad_contract = migrations_dir / "003_bad_contract0.py"
        if bad_contract.exists():
            result = validator.validate_migration_file(bad_contract)
            assert result["valid"] is False, "003_bad_contract0.py should be invalid"
            violations = [v["type"] for v in result["violations"]]
            assert "INVALID_PHASE_OPERATION" in violations
            # The validator currently flags MISSING_DATA_CHECK as a violation in strict mode
            # or if added to violations list
            assert "MISSING_DATA_CHECK" in violations

    def test_legacy_migrations_flagged(self):
        """Ensure legacy migrations are flagged for missing phase markers.

        This confirms the validator catches them.
        """
        workspace_root = Path(__file__).resolve().parents[5]
        migrations_dir = workspace_root / "src/backend/base/langflow/alembic/versions"

        validator = MigrationValidator(strict_mode=False)

        # Pick a random legacy migration
        legacy_migration = next(
            (f for f in migrations_dir.glob("*.py") if not f.name.startswith("00") and f.name != "__init__.py"), None
        )

        if legacy_migration:
            result = validator.validate_migration_file(legacy_migration)
            assert result["valid"] is False
            violations = [v["type"] for v in result["violations"]]
            assert "NO_PHASE_MARKER" in violations
