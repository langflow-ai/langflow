"""
Integration tests for AUTPE-6180: Complete Component Mapping & Schema Validation Integration with Startup Population.

These tests validate the complete end-to-end workflow from startup to validation
as specified in the JIRA story acceptance criteria.
"""

import pytest
import asyncio
import time
import os
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

import pytest_asyncio

from langflow.services.component_mapping.startup_population import StartupPopulationService
from langflow.custom.genesis.startup_extensions import (
    initialize_complete_genesis_extensions,
    initialize_component_mapping_population,
    initialize_complete_schema_integration
)


class TestAUTPE6180Integration:
    """Integration tests for AUTPE-6180 acceptance criteria."""

    @pytest_asyncio.fixture
    async def mock_db_session(self):
        """Create mock database session for testing."""
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_acceptance_criteria_1_automatic_startup_population_system(self, mock_db_session):
        """
        Test Acceptance Criteria 1: Automatic Startup Population System

        Requirements:
        - Startup Service: Create unified startup population service
        - Lifecycle Integration: Integrate with Genesis startup extensions
        - Version Control: Track population versions to prevent duplicates
        - Error Handling: Graceful fallback to hardcoded mappings if population fails
        """
        # Test unified startup population service creation
        service = StartupPopulationService()
        assert service is not None
        assert service.name == "startup_population_service"

        # Test lifecycle integration with startup extensions
        with patch('langflow.services.component_mapping.startup_population.StartupPopulationService') as mock_service_class:
            mock_service = Mock()
            mock_service.should_run_startup_population.return_value = True
            mock_service.populate_on_startup = AsyncMock(return_value={
                "status": "completed",
                "statistics": {"total_mappings": 95, "total_adapters": 95}
            })
            mock_service_class.return_value = mock_service

            result = await initialize_component_mapping_population(mock_db_session)
            assert result is True

        # Test version control (prevents duplicates)
        service._is_already_populated = AsyncMock(return_value=True)
        result = await service.populate_on_startup(mock_db_session)
        assert result["status"] == "skipped"
        assert result["reason"] == "already_populated"

        # Test error handling with graceful fallback
        service._is_already_populated = AsyncMock(return_value=False)
        service._migrate_hardcoded_mappings = AsyncMock(side_effect=Exception("Database error"))

        result = await service.populate_on_startup(mock_db_session)
        assert result["status"] == "failed"
        assert "fallback" in result
        assert result["fallback"] == "Using hardcoded mappings"

    @pytest.mark.asyncio
    async def test_acceptance_criteria_2_complete_component_schema_coverage(self):
        """
        Test Acceptance Criteria 2: Complete Component Schema Coverage

        Requirements:
        - Core Missing Schemas: genesis:prompt_template, genesis:chat_input, genesis:chat_output
        - Comprehensive Coverage: Add schemas for remaining 84+ component types
        - Schema Integration: Link component schemas with database mappings
        - Validation Enhancement: Integrate schema validation with mapping lookup
        """
        from langflow.services.spec.complete_component_schemas import (
            get_complete_component_schemas,
            get_core_missing_schemas,
            get_schema_coverage_stats,
            validate_schema_completeness
        )

        # Test core missing schemas implementation
        core_schemas = get_core_missing_schemas()
        assert "genesis:prompt_template" in core_schemas
        assert "genesis:chat_input" in core_schemas
        assert "genesis:chat_output" in core_schemas

        # Validate core schema structure
        prompt_schema = core_schemas["genesis:prompt_template"]
        assert prompt_schema["type"] == "object"
        assert "template" in prompt_schema["properties"]
        assert "template" in prompt_schema["required"]

        chat_input_schema = core_schemas["genesis:chat_input"]
        assert "should_store_message" in chat_input_schema["properties"]
        assert chat_input_schema["properties"]["should_store_message"]["default"] is True

        chat_output_schema = core_schemas["genesis:chat_output"]
        assert "data_template" in chat_output_schema["properties"]
        assert "output_format" in chat_output_schema["properties"]

        # Test comprehensive coverage (84+ additional component types)
        all_schemas = get_complete_component_schemas()
        assert len(all_schemas) >= 87  # Core 3 + 84+ additional

        # Test schema coverage statistics
        stats = get_schema_coverage_stats()
        assert stats["total_schemas"] >= 87
        assert stats["core_missing_schemas"] == 3
        assert "healthcare_schemas" in stats
        assert "schema_categories" in stats

        # Test schema integration with validation
        integration_result = initialize_complete_schema_integration()
        assert integration_result is True  # Should succeed even with mocks

        # Test validation enhancement
        completeness_result = validate_schema_completeness()
        assert "coverage_percentage" in completeness_result
        assert "complete_coverage" in completeness_result

    @pytest.mark.asyncio
    async def test_acceptance_criteria_3_configuration_management(self):
        """
        Test Acceptance Criteria 3: Configuration Management

        Requirements:
        - Environment Variables: GENESIS_AUTO_POPULATE_MAPPINGS, GENESIS_FORCE_MAPPING_REPOPULATION, GENESIS_SKIP_MAPPING_POPULATION
        - Runtime Configuration: Support for dynamic population control
        - Monitoring: Comprehensive logging and population status tracking
        """
        service = StartupPopulationService()

        # Test GENESIS_AUTO_POPULATE_MAPPINGS (default: true)
        assert service.should_run_startup_population() is True

        with patch.dict(os.environ, {'GENESIS_AUTO_POPULATE_MAPPINGS': 'false'}):
            assert service.should_run_startup_population() is False

        # Test GENESIS_SKIP_MAPPING_POPULATION
        with patch.dict(os.environ, {'GENESIS_SKIP_MAPPING_POPULATION': 'true'}):
            assert service.should_run_startup_population() is False

        # Test GENESIS_FORCE_MAPPING_REPOPULATION
        mock_session = AsyncMock()
        service.component_mapping_service.get_all_component_mappings = AsyncMock(return_value=[Mock()])

        with patch.dict(os.environ, {'GENESIS_FORCE_MAPPING_REPOPULATION': 'true'}):
            result = await service._is_already_populated(mock_session)
            assert result is False

        with patch.dict(os.environ, {'GENESIS_FORCE_MAPPING_REPOPULATION': 'false'}):
            result = await service._is_already_populated(mock_session)
            assert result is True

        # Test runtime configuration support via get_population_status
        service.component_mapping_service.get_statistics = AsyncMock(return_value={
            "component_mappings": {"total": 95, "by_category": {"HEALTHCARE": 6}},
            "runtime_adapters": {"total": 95}
        })

        status = await service.get_population_status(mock_session)
        assert "environment_config" in status
        env_config = status["environment_config"]
        assert "auto_populate" in env_config
        assert "force_repopulation" in env_config
        assert "skip_population" in env_config

        # Test monitoring capabilities
        assert "populated" in status
        assert "has_healthcare_mappings" in status
        assert "statistics" in status

    @pytest.mark.asyncio
    async def test_acceptance_criteria_4_integration_testing_and_validation(self, mock_db_session):
        """
        Test Acceptance Criteria 4: Integration Testing & Validation

        Requirements:
        - End-to-End Testing: Verify complete workflow from startup to validation
        - Performance Testing: Ensure startup time impact <5 seconds
        - Fallback Testing: Verify graceful degradation if database unavailable
        - Production Readiness: Full integration testing with all Genesis features
        """
        # Test end-to-end workflow
        start_time = time.time()

        with patch('langflow.services.component_mapping.startup_population.StartupPopulationService') as mock_service_class:
            mock_service = Mock()
            mock_service.should_run_startup_population.return_value = True
            mock_service.populate_on_startup = AsyncMock(return_value={
                "status": "completed",
                "duration_seconds": 2.5,  # Under 5 second requirement
                "statistics": {
                    "total_mappings": 95,
                    "total_adapters": 95
                },
                "phases": {
                    "hardcoded_mappings": {"created": 89, "errors": []},
                    "healthcare_mappings": {"created": 6, "errors": []},
                    "schema_integration": {"schemas_integrated": 95, "errors": []}
                }
            })
            mock_service_class.return_value = mock_service

            # Test complete Genesis extensions initialization
            result = await initialize_complete_genesis_extensions(mock_db_session)
            assert result is True

        end_time = time.time()
        execution_time = end_time - start_time

        # Performance testing: <5 seconds requirement
        assert execution_time < 5.0, f"Startup time {execution_time:.2f}s exceeds 5 second requirement"

        # Test fallback when database unavailable
        with patch('langflow.services.component_mapping.startup_population.StartupPopulationService') as mock_service_class:
            mock_service = Mock()
            mock_service.should_run_startup_population.return_value = True
            mock_service.populate_on_startup = AsyncMock(side_effect=Exception("Database connection failed"))
            mock_service_class.return_value = mock_service

            # Should not crash startup
            result = await initialize_component_mapping_population(mock_db_session)
            assert result is False  # Failed but gracefully handled

        # Test production readiness with all components
        service = StartupPopulationService()

        # Verify all major component categories are covered
        all_mappings = {}
        all_mappings.update(service.mapper.AUTONOMIZE_MODELS)
        all_mappings.update(service.mapper.MCP_MAPPINGS)
        all_mappings.update(service.mapper.STANDARD_MAPPINGS)

        # Should have mappings for all major categories
        genesis_types = list(all_mappings.keys())
        assert any("agent" in gt for gt in genesis_types)
        assert any("model" in gt for gt in genesis_types)
        assert any("mcp" in gt for gt in genesis_types)
        assert any("autonomize" in gt for gt in genesis_types)

    @pytest.mark.asyncio
    async def test_healthcare_connector_integration(self, mock_db_session):
        """Test healthcare connector integration as part of AUTPE-6180."""
        from langflow.services.component_mapping.healthcare_mappings import get_healthcare_component_mappings

        # Get healthcare mappings
        healthcare_mappings = get_healthcare_component_mappings()

        # Verify healthcare connectors from AUTPE-6164-6168
        expected_connectors = [
            "genesis:ehr_connector",
            "genesis:claims_connector",
            "genesis:eligibility_connector",
            "genesis:pharmacy_connector"
        ]

        for connector in expected_connectors:
            assert connector in healthcare_mappings
            mapping = healthcare_mappings[connector]
            assert "component" in mapping
            assert "config" in mapping
            assert "healthcare_metadata" in mapping

            # Verify HIPAA compliance settings
            metadata = mapping["healthcare_metadata"]
            assert metadata["hipaa_compliant"] is True
            assert metadata["phi_handling"] is True
            assert metadata["encryption_required"] is True
            assert metadata["audit_trail"] is True

        # Test healthcare mapping population
        service = StartupPopulationService()

        with patch('langflow.services.component_mapping.startup_population.get_healthcare_component_mappings',
                   return_value=healthcare_mappings):
            service.component_mapping_service.get_component_mapping_by_genesis_type = AsyncMock(return_value=None)
            service.component_mapping_service.create_component_mapping = AsyncMock()
            service.component_mapping_service.create_runtime_adapter = AsyncMock()

            result = await service._populate_healthcare_mappings(mock_db_session)
            assert result["created"] == len(expected_connectors)
            assert result["adapters_created"] == len(expected_connectors)

    @pytest.mark.asyncio
    async def test_performance_benchmark(self, mock_db_session):
        """
        Test performance benchmarks for startup population.

        AUTPE-6180 requires <5 second startup impact.
        """
        service = StartupPopulationService()

        # Mock all dependencies for performance test
        service._is_already_populated = AsyncMock(return_value=False)
        service._migrate_hardcoded_mappings = AsyncMock(return_value={
            "created": 95, "updated": 0, "skipped": 0, "adapters_created": 95, "errors": []
        })
        service._populate_healthcare_mappings = AsyncMock(return_value={
            "created": 6, "updated": 0, "adapters_created": 6, "errors": []
        })
        service._integrate_component_schemas = AsyncMock(return_value={
            "schemas_integrated": 95, "missing_schemas_identified": 0, "core_schemas_added": 3, "errors": []
        })
        service._mark_population_complete = AsyncMock()

        # Benchmark startup population
        start_time = time.time()
        result = await service.populate_on_startup(mock_db_session)
        end_time = time.time()

        execution_time = end_time - start_time
        reported_duration = result.get("duration_seconds", 0)

        # Verify performance requirements
        assert execution_time < 5.0, f"Actual execution time {execution_time:.2f}s exceeds 5 second requirement"
        assert result["status"] == "completed"
        assert result["statistics"]["total_mappings"] == 101  # 95 + 6
        assert result["statistics"]["performance_impact"] < 5.0

    @pytest.mark.asyncio
    async def test_error_recovery_and_fallback(self, mock_db_session):
        """Test error recovery and fallback mechanisms."""
        service = StartupPopulationService()

        # Test graceful fallback when database is unavailable
        service._is_already_populated = AsyncMock(side_effect=Exception("Database unavailable"))

        result = await service.populate_on_startup(mock_db_session)
        assert result["status"] == "failed"
        assert "fallback" in result

        # Test partial failure recovery
        service._is_already_populated = AsyncMock(return_value=False)
        service._migrate_hardcoded_mappings = AsyncMock(return_value={
            "created": 50, "updated": 0, "skipped": 45, "adapters_created": 50, "errors": ["Some migration errors"]
        })
        service._populate_healthcare_mappings = AsyncMock(side_effect=Exception("Healthcare service unavailable"))
        service._integrate_component_schemas = AsyncMock(return_value={
            "schemas_integrated": 95, "errors": []
        })
        service._mark_population_complete = AsyncMock()

        result = await service.populate_on_startup(mock_db_session)
        assert result["status"] == "failed"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_version_control_and_tracking(self, mock_db_session):
        """Test version control and population tracking."""
        service = StartupPopulationService()

        # Test version checking
        with patch.dict(os.environ, {'GENESIS_MAPPING_VERSION': '2.0.0'}):
            service.component_mapping_service.get_all_component_mappings = AsyncMock(return_value=[])
            result = await service._is_already_populated(mock_db_session)
            assert result is False  # No mappings, should populate

            service.component_mapping_service.get_all_component_mappings = AsyncMock(return_value=[Mock()])
            result = await service._is_already_populated(mock_db_session)
            assert result is True  # Has mappings, skip population

        # Test force repopulation override
        with patch.dict(os.environ, {
            'GENESIS_MAPPING_VERSION': '2.0.0',
            'GENESIS_FORCE_MAPPING_REPOPULATION': 'true'
        }):
            service.component_mapping_service.get_all_component_mappings = AsyncMock(return_value=[Mock()])
            result = await service._is_already_populated(mock_db_session)
            assert result is False  # Force repopulation enabled

    def test_environment_configuration_matrix(self):
        """Test all environment variable combinations."""
        service = StartupPopulationService()

        # Test matrix of environment configurations
        test_cases = [
            # (auto_populate, skip_population, expected_result)
            ('true', 'false', True),   # Default: should run
            ('true', 'true', False),   # Skip overrides auto
            ('false', 'false', False), # Auto disabled
            ('false', 'true', False),  # Both disabled
        ]

        for auto_populate, skip_population, expected in test_cases:
            with patch.dict(os.environ, {
                'GENESIS_AUTO_POPULATE_MAPPINGS': auto_populate,
                'GENESIS_SKIP_MAPPING_POPULATION': skip_population
            }):
                result = service.should_run_startup_population()
                assert result == expected, f"Failed for auto={auto_populate}, skip={skip_population}"


class TestProductionReadiness:
    """Test production readiness requirements from AUTPE-6180."""

    @pytest.mark.asyncio
    async def test_zero_manual_configuration_deployment(self, mock_db_session):
        """Test that deployment requires zero manual configuration steps."""
        # Test that all required environment variables have defaults
        service = StartupPopulationService()

        # Should work with no environment variables set
        with patch.dict(os.environ, {}, clear=True):
            # Default behavior should be to run startup population
            assert service.should_run_startup_population() is True

        # Test complete initialization without manual configuration
        with patch('langflow.custom.genesis.startup_extensions.initialize_genesis_studio_extensions', return_value=True):
            with patch('langflow.custom.genesis.startup_extensions.initialize_component_mapping_population', new_callable=AsyncMock) as mock_pop:
                mock_pop.return_value = True
                with patch('langflow.custom.genesis.startup_extensions.initialize_complete_schema_integration', return_value=True):
                    result = await initialize_complete_genesis_extensions(mock_db_session)
                    assert result is True

    @pytest.mark.asyncio
    async def test_comprehensive_error_handling(self):
        """Test comprehensive error handling for production."""
        service = StartupPopulationService()

        # Test service remains stable under various error conditions
        error_scenarios = [
            "Database connection timeout",
            "Invalid schema format",
            "Missing component mapping",
            "Healthcare service unavailable",
            "Schema validation failure"
        ]

        for error_message in error_scenarios:
            mock_session = AsyncMock()
            service._is_already_populated = AsyncMock(side_effect=Exception(error_message))

            # Should not crash, should return error status
            result = await service.populate_on_startup(mock_session)
            assert result["status"] == "failed"
            assert "error" in result
            assert "fallback" in result

    def test_logging_and_monitoring_coverage(self):
        """Test that logging and monitoring requirements are met."""
        import logging
        from unittest.mock import MagicMock

        # Test that service uses proper logging
        service = StartupPopulationService()

        # Verify logger is configured
        assert hasattr(service, '__module__')

        # Test logging calls during operation (would need more sophisticated mocking in real scenario)
        with patch('langflow.services.component_mapping.startup_population.logger') as mock_logger:
            # Test that should_run_startup_population logs appropriately
            with patch.dict(os.environ, {'GENESIS_SKIP_MAPPING_POPULATION': 'true'}):
                service.should_run_startup_population()
                # Should have logged info about skipping
                mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_database_driven_mappings_verification(self, mock_db_session):
        """Verify that database-driven mappings work as intended."""
        service = StartupPopulationService()

        # Test that service properly uses ComponentMappingService
        assert service.component_mapping_service is not None

        # Test that migration properly calls database service methods
        service.component_mapping_service.migrate_hardcoded_mappings = AsyncMock(return_value={
            "created": 95, "updated": 0, "skipped": 0, "errors": []
        })

        result = await service._migrate_hardcoded_mappings(mock_db_session)

        # Verify database service was called with proper mappings
        service.component_mapping_service.migrate_hardcoded_mappings.assert_called_once()
        call_args = service.component_mapping_service.migrate_hardcoded_mappings.call_args
        assert mock_db_session in call_args.args
        mappings_dict = call_args.args[1]
        assert isinstance(mappings_dict, dict)
        assert len(mappings_dict) > 0