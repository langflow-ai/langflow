"""
Unit tests for StartupPopulationService.

Tests the unified startup population system that combines hardcoded mapping migration,
healthcare connector mappings, and component schema validation integration (AUTPE-6180).
"""

import pytest
import os
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

import pytest_asyncio

from langflow.services.component_mapping.startup_population import StartupPopulationService
from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentMappingCreate,
    ComponentCategoryEnum,
)


class TestStartupPopulationService:
    """Test cases for StartupPopulationService."""

    @pytest_asyncio.fixture
    async def service(self):
        """Create StartupPopulationService instance for testing."""
        return StartupPopulationService()

    @pytest_asyncio.fixture
    async def mock_session(self):
        """Create mock database session."""
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_service_initialization(self, service):
        """Test service initializes correctly."""
        assert service.name == "startup_population_service"
        assert service.component_mapping_service is not None
        assert service.mapper is not None

    @pytest.mark.asyncio
    async def test_should_run_startup_population_default(self, service):
        """Test should_run_startup_population with default settings."""
        # Default should be True
        assert service.should_run_startup_population() is True

    @pytest.mark.asyncio
    async def test_should_run_startup_population_disabled(self, service):
        """Test should_run_startup_population when disabled."""
        with patch.dict(os.environ, {'GENESIS_SKIP_MAPPING_POPULATION': 'true'}):
            assert service.should_run_startup_population() is False

        with patch.dict(os.environ, {'GENESIS_AUTO_POPULATE_MAPPINGS': 'false'}):
            assert service.should_run_startup_population() is False

    @pytest.mark.asyncio
    async def test_populate_on_startup_already_populated(self, service, mock_session):
        """Test populate_on_startup when already populated."""
        # Mock already populated
        service._is_already_populated = AsyncMock(return_value=True)

        result = await service.populate_on_startup(mock_session)

        assert result["status"] == "skipped"
        assert result["reason"] == "already_populated"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_populate_on_startup_complete_flow(self, service, mock_session):
        """Test complete populate_on_startup flow."""
        # Mock not already populated
        service._is_already_populated = AsyncMock(return_value=False)

        # Mock phase methods
        service._migrate_hardcoded_mappings = AsyncMock(return_value={
            "created": 50,
            "updated": 5,
            "skipped": 10,
            "adapters_created": 50,
            "errors": []
        })

        service._populate_healthcare_mappings = AsyncMock(return_value={
            "created": 6,
            "updated": 0,
            "adapters_created": 6,
            "errors": []
        })

        service._integrate_component_schemas = AsyncMock(return_value={
            "schemas_integrated": 95,
            "missing_schemas_identified": 0,
            "core_schemas_added": 3,
            "errors": []
        })

        service._mark_population_complete = AsyncMock()

        result = await service.populate_on_startup(mock_session)

        assert result["status"] == "completed"
        assert "duration_seconds" in result
        assert "phases" in result
        assert "statistics" in result

        # Check statistics
        stats = result["statistics"]
        assert stats["total_mappings"] == 56  # 50 + 6
        assert stats["total_adapters"] == 56  # 50 + 6

        # Verify all phase methods were called
        service._migrate_hardcoded_mappings.assert_called_once_with(mock_session)
        service._populate_healthcare_mappings.assert_called_once_with(mock_session)
        service._integrate_component_schemas.assert_called_once_with(mock_session)
        service._mark_population_complete.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_populate_on_startup_with_errors(self, service, mock_session):
        """Test populate_on_startup handles errors gracefully."""
        # Mock not already populated
        service._is_already_populated = AsyncMock(return_value=False)

        # Mock error in migration
        service._migrate_hardcoded_mappings = AsyncMock(side_effect=Exception("Migration error"))

        result = await service.populate_on_startup(mock_session)

        assert result["status"] == "failed"
        assert "error" in result
        assert "fallback" in result

    @pytest.mark.asyncio
    async def test_migrate_hardcoded_mappings(self, service, mock_session):
        """Test hardcoded mappings migration."""
        # Mock component mapping service
        service.component_mapping_service.migrate_hardcoded_mappings = AsyncMock(return_value={
            "created": 95,
            "updated": 0,
            "skipped": 0,
            "errors": []
        })

        result = await service._migrate_hardcoded_mappings(mock_session)

        assert result["created"] == 95
        assert result["adapters_created"] == 95
        assert len(result["errors"]) == 0

        # Verify mapper mappings were used
        service.component_mapping_service.migrate_hardcoded_mappings.assert_called_once()
        call_args = service.component_mapping_service.migrate_hardcoded_mappings.call_args
        assert mock_session in call_args.args
        mappings_dict = call_args.args[1]
        assert len(mappings_dict) > 0  # Should have mappings from all three categories

    @pytest.mark.asyncio
    async def test_populate_healthcare_mappings(self, service, mock_session):
        """Test healthcare mappings population."""
        # Mock healthcare mappings
        mock_healthcare_mappings = {
            "genesis:ehr_connector": {
                "component": "EHRConnector",
                "config": {"ehr_system": "epic"},
                "category": ComponentCategoryEnum.HEALTHCARE
            },
            "genesis:claims_connector": {
                "component": "ClaimsConnector",
                "config": {"clearinghouse": "change_healthcare"},
                "category": ComponentCategoryEnum.HEALTHCARE
            }
        }

        with patch('langflow.services.component_mapping.startup_population.get_healthcare_component_mappings',
                   return_value=mock_healthcare_mappings):

            # Mock service methods
            service.component_mapping_service.get_component_mapping_by_genesis_type = AsyncMock(return_value=None)
            service.component_mapping_service.create_component_mapping = AsyncMock()
            service.component_mapping_service.create_runtime_adapter = AsyncMock()

            result = await service._populate_healthcare_mappings(mock_session)

            assert result["created"] == 2
            assert result["adapters_created"] == 2
            assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_integrate_component_schemas(self, service, mock_session):
        """Test component schema integration."""
        # Mock component mappings
        mock_mappings = [
            Mock(genesis_type="genesis:agent"),
            Mock(genesis_type="genesis:chat_input"),
            Mock(genesis_type="genesis:prompt_template")
        ]

        service.component_mapping_service.get_all_component_mappings = AsyncMock(
            return_value=mock_mappings
        )

        # Mock schema integration
        service._add_missing_core_schemas = AsyncMock(return_value={"added": 3})
        service._has_validation_schema = Mock(return_value=True)

        result = await service._integrate_component_schemas(mock_session)

        assert result["schemas_integrated"] == 3
        assert result["missing_schemas_identified"] == 0
        assert result["core_schemas_added"] == 3

    @pytest.mark.asyncio
    async def test_get_population_status(self, service, mock_session):
        """Test get_population_status method."""
        # Mock statistics
        mock_stats = {
            "component_mappings": {
                "total": 100,
                "by_category": {"HEALTHCARE": 6}
            },
            "runtime_adapters": {
                "total": 100,
                "by_runtime": {"LANGFLOW": 100}
            }
        }

        service.component_mapping_service.get_statistics = AsyncMock(return_value=mock_stats)

        result = await service.get_population_status(mock_session)

        assert result["populated"] is True
        assert result["has_healthcare_mappings"] is True
        assert result["statistics"] == mock_stats
        assert "environment_config" in result

    @pytest.mark.asyncio
    async def test_cleanup_population_data_not_allowed(self, service, mock_session):
        """Test cleanup_population_data when not allowed."""
        with pytest.raises(ValueError, match="Cleanup not allowed"):
            await service.cleanup_population_data(mock_session)

    @pytest.mark.asyncio
    async def test_cleanup_population_data_allowed(self, service, mock_session):
        """Test cleanup_population_data when allowed."""
        with patch.dict(os.environ, {'GENESIS_ALLOW_CLEANUP': 'true'}):
            # Mock mappings and adapters
            mock_mapping = Mock(id="mapping1", genesis_type="genesis:agent")
            mock_adapter = Mock(id="adapter1")

            service.component_mapping_service.get_all_component_mappings = AsyncMock(
                return_value=[mock_mapping]
            )
            service.component_mapping_service.get_all_adapters_for_genesis_type = AsyncMock(
                return_value=[mock_adapter]
            )
            service.component_mapping_service.delete_runtime_adapter = AsyncMock()
            service.component_mapping_service.delete_component_mapping = AsyncMock()

            result = await service.cleanup_population_data(mock_session)

            assert result["deleted_mappings"] == 1
            assert result["deleted_adapters"] == 1

    @pytest.mark.asyncio
    async def test_is_already_populated_force_repopulation(self, service, mock_session):
        """Test _is_already_populated with force repopulation flag."""
        # Mock existing mappings
        service.component_mapping_service.get_all_component_mappings = AsyncMock(
            return_value=[Mock()]
        )

        with patch.dict(os.environ, {'GENESIS_FORCE_MAPPING_REPOPULATION': 'true'}):
            result = await service._is_already_populated(mock_session)
            assert result is False

        with patch.dict(os.environ, {'GENESIS_FORCE_MAPPING_REPOPULATION': 'false'}):
            result = await service._is_already_populated(mock_session)
            assert result is True

    @pytest.mark.asyncio
    async def test_determine_healthcare_connector_type(self, service):
        """Test _determine_healthcare_connector_type method."""
        assert service._determine_healthcare_connector_type("genesis:ehr_connector") == "ehr_connector"
        assert service._determine_healthcare_connector_type("genesis:claims_connector") == "claims_connector"
        assert service._determine_healthcare_connector_type("genesis:eligibility_connector") == "eligibility_connector"
        assert service._determine_healthcare_connector_type("genesis:pharmacy_connector") == "pharmacy_connector"
        assert service._determine_healthcare_connector_type("genesis:unknown_connector") == "generic_healthcare_connector"

    @pytest.mark.asyncio
    async def test_extract_healthcare_io_mapping(self, service):
        """Test _extract_healthcare_io_mapping method."""
        mapping_info = {
            "component": "EHRConnector",
            "dataType": "Data"
        }

        result = service._extract_healthcare_io_mapping(mapping_info)

        assert result["component"] == "EHRConnector"
        assert result["dataType"] == "Data"
        assert result["healthcare_specific"] is True
        assert result["input_field"] == "input_value"
        assert result["output_field"] == "response"

    def test_environment_variable_parsing(self, service):
        """Test environment variable parsing in various methods."""
        # Test auto populate (default true)
        assert service.should_run_startup_population() is True

        # Test with explicit false
        with patch.dict(os.environ, {'GENESIS_AUTO_POPULATE_MAPPINGS': 'false'}):
            assert service.should_run_startup_population() is False

        # Test with skip flag
        with patch.dict(os.environ, {'GENESIS_SKIP_MAPPING_POPULATION': 'true'}):
            assert service.should_run_startup_population() is False


class TestStartupPopulationIntegration:
    """Integration tests for startup population."""

    @pytest.mark.asyncio
    async def test_complete_integration_flow(self):
        """Test complete integration flow from startup extensions."""
        # This would be an integration test that verifies the complete flow
        # from startup_extensions.py to the population service
        pass

    @pytest.mark.asyncio
    async def test_schema_integration_with_validation_service(self):
        """Test schema integration with the spec validation service."""
        # This would test that schemas are properly integrated with the validation system
        pass

    @pytest.mark.asyncio
    async def test_performance_requirements(self):
        """Test that startup population meets performance requirements (<5 seconds)."""
        # This would test the performance requirement from AUTPE-6180
        pass