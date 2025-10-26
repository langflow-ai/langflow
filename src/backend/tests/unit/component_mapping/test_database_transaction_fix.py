"""
Test for database transaction rollback fix.

This test validates that the fix for AUTPE-6199 prevents cascade failures
when individual database operations fail during component mapping migration.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from langflow.services.component_mapping.service import ComponentMappingService
from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentMappingCreate,
    ComponentCategoryEnum,
)
from langflow.services.database.models.component_mapping.runtime_adapter import (
    RuntimeAdapter,
    RuntimeAdapterCreate,
    RuntimeTypeEnum,
)


class TestDatabaseTransactionFix:
    """Test database transaction isolation and error handling fixes."""

    @pytest.fixture
    def service(self):
        """Create component mapping service."""
        return ComponentMappingService()

    @pytest.fixture
    def mock_session(self):
        """Create mock database session with savepoint support."""
        session = AsyncMock()

        # Mock savepoint behavior
        savepoint = AsyncMock()
        savepoint.commit = AsyncMock()
        savepoint.rollback = AsyncMock()
        session.begin_nested = AsyncMock(return_value=savepoint)

        return session

    @pytest.fixture
    def valid_mapping_data(self):
        """Create valid mapping data for testing."""
        return {
            "genesis:test_component": {
                "component": "TestComponent",
                "config": {"param1": "value1"},
                "dataType": "Data"
            }
        }

    @pytest.fixture
    def invalid_mapping_data(self):
        """Create mapping data that will cause validation errors."""
        return {
            "invalid_genesis_type": {  # Missing "genesis:" prefix
                "component": "InvalidComponent",
                "config": {"param1": "value1"},
                "dataType": "Data"
            },
            "genesis:valid_component": {
                "component": "ValidComponent",
                "config": {"param1": "value1"},
                "dataType": "Data"
            }
        }

    @pytest.mark.asyncio
    async def test_transaction_isolation_with_validation_errors(self, service, mock_session, invalid_mapping_data):
        """Test that validation errors in one mapping don't abort the entire transaction."""

        # Mock the get_component_mapping_by_genesis_type to return None (no existing mappings)
        service.get_component_mapping_by_genesis_type = AsyncMock(return_value=None)

        # Mock the create operations to succeed when called without commit
        service.create_component_mapping = AsyncMock(return_value=AsyncMock())
        service.create_runtime_adapter = AsyncMock(return_value=AsyncMock())
        service.get_runtime_adapter_for_genesis_type = AsyncMock(return_value=None)

        # Call the migration method
        result = await service.migrate_hardcoded_mappings(
            mock_session, invalid_mapping_data, overwrite_existing=False
        )

        # Verify that both mappings succeeded due to automatic genesis type correction
        assert result["created"] == 2  # Both should be created after correction
        assert len(result["errors"]) == 0  # No errors due to automatic correction

        # Verify savepoints were used (begin_nested called twice, once per mapping)
        assert mock_session.begin_nested.call_count == 2

    @pytest.mark.asyncio
    async def test_transaction_isolation_with_database_errors(self, service, mock_session, valid_mapping_data):
        """Test that database errors in one operation don't abort subsequent operations."""

        # Mock database operations to fail on first call, succeed on second
        call_count = 0

        async def mock_create_with_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Database constraint violation")
            return AsyncMock()

        service.get_component_mapping_by_genesis_type = AsyncMock(return_value=None)
        service.create_component_mapping = AsyncMock(side_effect=mock_create_with_failure)
        service.create_runtime_adapter = AsyncMock(return_value=AsyncMock())
        service.get_runtime_adapter_for_genesis_type = AsyncMock(return_value=None)

        # Add a second valid mapping to test continued processing
        test_data = {
            "genesis:failing_component": valid_mapping_data["genesis:test_component"],
            "genesis:succeeding_component": valid_mapping_data["genesis:test_component"]
        }

        result = await service.migrate_hardcoded_mappings(
            mock_session, test_data, overwrite_existing=False
        )

        # Verify that one failed and one succeeded
        assert result["created"] == 1  # Second one should succeed
        assert len(result["errors"]) == 1  # First one should fail

        # Verify the error contains the expected failure message
        error_message = result["errors"][0]
        assert "genesis:failing_component" in error_message
        assert "Database constraint violation" in error_message

    @pytest.mark.asyncio
    async def test_savepoint_rollback_on_validation_error(self, service, mock_session):
        """Test that savepoints are properly rolled back on validation errors."""

        # Create mapping data that will cause a real validation error
        # Using invalid version format which should fail ComponentMappingCreate validation
        invalid_data = {
            "genesis:test_component": {
                "component": "TestComponent",
                "config": {},
                "dataType": "Data"
            }
        }

        service.get_component_mapping_by_genesis_type = AsyncMock(return_value=None)

        # Mock ComponentMappingCreate to raise validation error
        with patch('langflow.services.component_mapping.service.ComponentMappingCreate') as mock_create:
            mock_create.side_effect = ValueError("Invalid version format")

            result = await service.migrate_hardcoded_mappings(
                mock_session, invalid_data, overwrite_existing=False
            )

            # Verify that the validation error was caught and handled
            assert result["created"] == 0
            assert len(result["errors"]) == 1
            assert "Validation error" in result["errors"][0]

            # Verify savepoint was created and rolled back
            mock_session.begin_nested.assert_called_once()
            savepoint = mock_session.begin_nested.return_value
            savepoint.rollback.assert_called_once()
            savepoint.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_savepoint_commit_on_success(self, service, mock_session, valid_mapping_data):
        """Test that savepoints are properly committed on successful operations."""

        service.get_component_mapping_by_genesis_type = AsyncMock(return_value=None)
        service.create_component_mapping = AsyncMock(return_value=AsyncMock())
        service.create_runtime_adapter = AsyncMock(return_value=AsyncMock())
        service.get_runtime_adapter_for_genesis_type = AsyncMock(return_value=None)

        result = await service.migrate_hardcoded_mappings(
            mock_session, valid_mapping_data, overwrite_existing=False
        )

        # Verify successful migration
        assert result["created"] == 1
        assert len(result["errors"]) == 0

        # Verify savepoint was created and committed
        mock_session.begin_nested.assert_called_once()
        savepoint = mock_session.begin_nested.return_value
        savepoint.commit.assert_called_once()
        savepoint.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_mapping_isolation(self, service, mock_session):
        """Test that multiple mappings are properly isolated using individual savepoints."""

        # Create test data with one valid and one invalid mapping
        mixed_data = {
            "genesis:valid_component": {
                "component": "ValidComponent",
                "config": {"param": "value"},
                "dataType": "Data"
            },
            "invalid_component": {  # Missing genesis: prefix
                "component": "InvalidComponent",
                "config": {"param": "value"},
                "dataType": "Data"
            },
            "genesis:another_valid": {
                "component": "AnotherValidComponent",
                "config": {"param": "value"},
                "dataType": "Data"
            }
        }

        service.get_component_mapping_by_genesis_type = AsyncMock(return_value=None)
        service.create_component_mapping = AsyncMock(return_value=AsyncMock())
        service.create_runtime_adapter = AsyncMock(return_value=AsyncMock())
        service.get_runtime_adapter_for_genesis_type = AsyncMock(return_value=None)

        result = await service.migrate_hardcoded_mappings(
            mock_session, mixed_data, overwrite_existing=False
        )

        # Verify that all mappings succeeded due to automatic genesis type correction
        assert result["created"] == 3  # All three components (invalid_component gets corrected)
        assert len(result["errors"]) == 0  # No errors due to automatic correction

        # Verify each mapping got its own savepoint
        assert mock_session.begin_nested.call_count == 3

    @pytest.mark.asyncio
    async def test_no_cascade_failure_with_commit_disabled(self, service, mock_session, valid_mapping_data):
        """Test that operations use commit=False to avoid premature commits."""

        service.get_component_mapping_by_genesis_type = AsyncMock(return_value=None)
        service.create_component_mapping = AsyncMock(return_value=AsyncMock())
        service.create_runtime_adapter = AsyncMock(return_value=AsyncMock())
        service.get_runtime_adapter_for_genesis_type = AsyncMock(return_value=None)

        await service.migrate_hardcoded_mappings(
            mock_session, valid_mapping_data, overwrite_existing=False
        )

        # Verify that create operations were called with commit=False
        service.create_component_mapping.assert_called_once()
        create_call_kwargs = service.create_component_mapping.call_args[1]
        assert create_call_kwargs.get("commit") is False

        service.create_runtime_adapter.assert_called_once()
        adapter_call_kwargs = service.create_runtime_adapter.call_args[1]
        assert adapter_call_kwargs.get("commit") is False