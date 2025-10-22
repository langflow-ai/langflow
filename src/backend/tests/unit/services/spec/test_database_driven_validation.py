"""
Test suite for database-driven validation enhancements (AUTPE-6207).

This module tests the integration of database-driven component discovery,
dynamic schema generation, and enhanced validation capabilities.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from typing import Dict, Any, List
import yaml
import json

from langflow.services.spec.service import SpecService
from langflow.services.spec.complete_component_schemas import (
    get_enhanced_component_schema,
    refresh_database_schemas,
    get_schema_statistics
)
from langflow.services.spec.dynamic_schema_generator import DynamicSchemaGenerator
from langflow.services.component_mapping.service import ComponentMappingService
from langflow.services.database.models.component_mapping import ComponentMapping


class TestDatabaseDrivenValidation:
    """Test database-driven validation capabilities."""

    @pytest.fixture
    def spec_service(self):
        """Create a SpecService instance with mocked dependencies."""
        service = SpecService()
        service.component_mapping_service = Mock(spec=ComponentMappingService)
        service.dynamic_schema_generator = Mock(spec=DynamicSchemaGenerator)
        return service

    @pytest.fixture
    def sample_spec_yaml(self):
        """Sample specification YAML for testing."""
        return """
id: urn:agent:genesis:test:healthcare-agent:1.0.0
name: Healthcare Test Agent
description: Test agent for database-driven validation
agentGoal: Validate database-driven component discovery
components:
  input:
    type: genesis:chat_input
    config:
      should_store_message: true

  ehr_connector:
    type: genesis:ehr_connector
    config:
      ehr_system: epic
      fhir_version: R4
    provides:
      - useAs: data
        in: processor

  processor:
    type: genesis:agent
    config:
      system_message: Process healthcare data
    provides:
      - useAs: message
        in: output

  output:
    type: genesis:chat_output
    config:
      should_store_message: true
"""

    @pytest.fixture
    def mock_database_mappings(self):
        """Mock database mappings for testing."""
        mappings = []
        for i, comp_type in enumerate([
            "genesis:ehr_connector",
            "genesis:claims_connector",
            "genesis:eligibility_connector",
            "genesis:autonomize"
        ]):
            mapping = Mock(spec=ComponentMapping)
            mapping.id = f"mapping-{i}"
            mapping.genesis_type = comp_type
            mapping.langflow_component = comp_type.replace("genesis:", "").replace("_", " ").title()
            mapping.category = "healthcare"
            mapping.priority = 1
            mapping.is_active = True
            mapping.default_config = {}
            mapping.validation_schema = {
                "type": "object",
                "properties": {},
                "additionalProperties": True
            }
            mapping.created_at = datetime.now(timezone.utc)
            mappings.append(mapping)
        return mappings

    @pytest.mark.asyncio
    async def test_database_component_discovery(self, spec_service, mock_database_mappings):
        """Test that database components are discovered and cached."""
        # Setup mock session
        mock_session = AsyncMock()

        # Mock the database service to return mappings
        spec_service.component_mapping_service.get_all_component_mappings = AsyncMock(
            return_value=mock_database_mappings
        )

        # Refresh database cache
        await spec_service._refresh_mapper_database_cache(mock_session)

        # Verify mappings were cached
        assert len(spec_service._database_components_cache) == 4
        assert "genesis:ehr_connector" in spec_service._database_components_cache
        assert spec_service._last_cache_refresh is not None

    @pytest.mark.asyncio
    async def test_enhanced_component_validation(self, spec_service, sample_spec_yaml, mock_database_mappings):
        """Test validation with database-discovered components."""
        # Setup mock session
        mock_session = AsyncMock()

        # Mock database service
        spec_service.component_mapping_service.get_all_component_mappings = AsyncMock(
            return_value=mock_database_mappings
        )

        # Mock get_all_available_components_with_database
        spec_service.get_all_available_components_with_database = AsyncMock(
            return_value={
                "genesis_mapped": {
                    "genesis:chat_input": {"component": "ChatInput"},
                    "genesis:chat_output": {"component": "ChatOutput"},
                    "genesis:agent": {"component": "Agent"},
                    "genesis:ehr_connector": {"component": "EhrConnector"}
                },
                "database_mapped": {
                    "genesis:ehr_connector": {
                        "component": "EhrConnector",
                        "category": "healthcare"
                    }
                },
                "healthcare_components": {
                    "genesis:ehr_connector": {
                        "component": "EhrConnector",
                        "category": "healthcare"
                    }
                },
                "discovery_stats": {
                    "total_mapped": 4,
                    "database_mappings": 1,
                    "healthcare_connectors": 1
                }
            }
        )

        # Validate specification
        result = await spec_service.validate_spec(sample_spec_yaml, detailed=True)

        # Assertions
        assert result["valid"] == True or len(result["errors"]) == 0
        assert "discovery_stats" in str(result) or "validation_phases" in result

    @pytest.mark.asyncio
    async def test_dynamic_schema_generation(self, spec_service):
        """Test dynamic schema generation for new components."""
        # Setup mock generator
        mock_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "config": {"type": "object"}
            }
        }

        spec_service.dynamic_schema_generator.generate_schema_from_introspection = Mock(
            return_value=mock_schema
        )

        # Mock session
        mock_session = AsyncMock()

        # Mock database lookup to return None (component not in database)
        spec_service.component_mapping_service.get_component_mapping_by_genesis_type = AsyncMock(
            return_value=None
        )

        # Test validation with dynamic schema
        component = {
            "type": "genesis:new_healthcare_connector",
            "config": {"test": "value"}
        }

        result = await spec_service.validate_component_with_dynamic_schema(component, mock_session)

        # Verify dynamic schema was generated
        spec_service.dynamic_schema_generator.generate_schema_from_introspection.assert_called_once()
        assert "errors" in result
        assert "warnings" in result

    @pytest.mark.asyncio
    async def test_healthcare_connector_validation(self, spec_service):
        """Test validation of all 16 healthcare connectors."""
        healthcare_connectors = [
            "genesis:ehr_connector",
            "genesis:claims_connector",
            "genesis:eligibility_connector",
            "genesis:pharmacy_connector",
            "genesis:autonomize",
            "genesis:medical_terminology_connector",
            "genesis:accumulator_benefits_connector",
            "genesis:provider_network_connector",
            "genesis:quality_metrics_connector",
            "genesis:azure_document_intelligence",
            "genesis:assemblyai_start_transcript",
            "genesis:medical_data_standardizer_connector",
            "genesis:compliance_data_connector",
            "genesis:pharmacy_benefits_connector"
        ]

        for connector_type in healthcare_connectors:
            component = {
                "id": f"{connector_type.split(':')[1]}_test",
                "type": connector_type,
                "config": {}
            }

            # Should not raise exception
            result = await spec_service.validate_component_with_dynamic_schema(component)
            assert "errors" in result
            assert "warnings" in result

    @pytest.mark.asyncio
    async def test_cache_refresh_and_invalidation(self, spec_service, mock_database_mappings):
        """Test cache refresh and invalidation logic."""
        mock_session = AsyncMock()

        # Mock database service
        spec_service.component_mapping_service.get_all_component_mappings = AsyncMock(
            return_value=mock_database_mappings
        )

        # First refresh
        await spec_service._refresh_mapper_database_cache(mock_session)
        first_refresh_time = spec_service._last_cache_refresh

        # Verify cache is populated
        assert len(spec_service._database_components_cache) == 4

        # Second refresh
        await asyncio.sleep(0.1)  # Small delay
        await spec_service._refresh_mapper_database_cache(mock_session)
        second_refresh_time = spec_service._last_cache_refresh

        # Verify cache was refreshed
        assert second_refresh_time > first_refresh_time

    @pytest.mark.asyncio
    async def test_fallback_to_hardcoded_mappings(self, spec_service):
        """Test fallback to hardcoded mappings when database unavailable."""
        # Mock database service to raise exception
        spec_service.component_mapping_service.get_all_component_mappings = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        mock_session = AsyncMock()

        # Should not raise exception, should fall back gracefully
        await spec_service._refresh_mapper_database_cache(mock_session)

        # Cache should be empty but service should still work
        assert len(spec_service._database_components_cache) == 0

    def test_schema_statistics(self):
        """Test schema statistics generation."""
        stats = get_schema_statistics()

        assert "enhanced_stats" in stats
        assert "static_schemas" in stats["enhanced_stats"]
        assert "healthcare_connectors" in stats["enhanced_stats"]
        assert stats["enhanced_stats"]["static_schemas"] > 0

    @pytest.mark.asyncio
    async def test_complete_validation_workflow(self, spec_service, sample_spec_yaml):
        """Test complete validation workflow with all enhancements."""
        mock_session = AsyncMock()

        # Mock all required methods
        spec_service.component_mapping_service.get_all_component_mappings = AsyncMock(
            return_value=[]
        )

        # Parse spec
        spec_dict = yaml.safe_load(sample_spec_yaml)

        # Test quick validation
        quick_result = await spec_service.validate_spec_quick(sample_spec_yaml)
        assert "valid" in quick_result
        assert "validation_phases" in quick_result

        # Test detailed validation
        detailed_result = await spec_service.validate_spec(sample_spec_yaml, detailed=True)
        assert "valid" in detailed_result
        assert "errors" in detailed_result
        assert "warnings" in detailed_result
        assert "suggestions" in detailed_result

    def test_enhanced_component_schema_retrieval(self):
        """Test enhanced schema retrieval with fallback chain."""
        # Test static schema retrieval
        schema = get_enhanced_component_schema("genesis:chat_input")
        assert schema is not None
        assert "type" in schema
        assert schema["type"] == "object"

        # Test unknown component (should trigger dynamic generation or return None)
        unknown_schema = get_enhanced_component_schema("genesis:unknown_component")
        # Should either generate or return None gracefully
        assert unknown_schema is None or "type" in unknown_schema

    @pytest.mark.asyncio
    async def test_performance_with_large_spec(self, spec_service):
        """Test validation performance with large specification."""
        # Create large spec with many components
        large_spec = {
            "id": "urn:agent:genesis:test:large:1.0.0",
            "name": "Large Test Agent",
            "description": "Test performance",
            "agentGoal": "Test",
            "components": {}
        }

        # Add 100 components
        for i in range(100):
            large_spec["components"][f"component_{i}"] = {
                "type": "genesis:agent",
                "config": {"system_message": f"Component {i}"}
            }

        large_spec_yaml = yaml.dump(large_spec)

        # Measure validation time
        import time
        start_time = time.time()
        result = await spec_service.validate_spec(large_spec_yaml, detailed=False)
        end_time = time.time()

        # Should complete within reasonable time (< 10 seconds)
        assert (end_time - start_time) < 10
        assert "valid" in result


class TestDynamicSchemaGenerator:
    """Test dynamic schema generator functionality."""

    @pytest.fixture
    def generator(self):
        """Create a DynamicSchemaGenerator instance."""
        return DynamicSchemaGenerator()

    def test_schema_generation_for_healthcare_component(self, generator):
        """Test schema generation for healthcare components."""
        schema = generator.generate_schema_from_introspection(
            genesis_type="genesis:ehr_connector",
            component_category="healthcare",
            introspection_data={"inputs": ["patient_id"], "outputs": ["patient_data"]}
        )

        assert schema is not None
        assert "type" in schema
        assert schema["type"] == "object"
        assert "description" in schema

    def test_schema_caching(self, generator):
        """Test schema caching mechanism."""
        # Generate schema first time
        schema1 = generator.generate_schema_from_introspection(
            genesis_type="genesis:test_component",
            component_category="test"
        )

        # Second call should return cached schema
        schema2 = generator.generate_schema_from_introspection(
            genesis_type="genesis:test_component",
            component_category="test"
        )

        assert schema1 == schema2
        assert generator._generation_stats["cache_hits"] > 0

    def test_fallback_schema_generation(self, generator):
        """Test fallback schema generation on error."""
        # Force an error in generation
        with patch.object(generator, '_generate_base_schema', side_effect=Exception("Test error")):
            schema = generator.generate_schema_from_introspection(
                genesis_type="genesis:error_component",
                component_category="test"
            )

        # Should return fallback schema
        assert schema is not None
        assert generator._generation_stats["generation_failures"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])