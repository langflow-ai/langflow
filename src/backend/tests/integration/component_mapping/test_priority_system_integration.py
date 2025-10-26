"""Integration tests for AUTPE-6199: Component Mapping Priority System Integration."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
import asyncio

from langflow.custom.genesis.spec.mapper import ComponentMapper
from langflow.services.spec.service import SpecService
from langflow.services.component_mapping.service import ComponentMappingService
from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentMappingCreate,
    ComponentCategoryEnum,
)


@pytest.fixture
def component_mapping_service():
    """Create a ComponentMappingService instance for testing."""
    return ComponentMappingService()


@pytest.fixture
def spec_service():
    """Create a SpecService instance for testing."""
    return SpecService()


@pytest.fixture
def component_mapper():
    """Create a ComponentMapper instance for testing."""
    return ComponentMapper()


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def real_database_mappings():
    """Create realistic database mappings for integration testing."""
    return [
        ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:custom_agent",
            base_config={
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2000,
                "custom_system_prompt": "You are a specialized healthcare agent."
            },
            io_mapping={
                "component": "CustomHealthcareAgent",
                "dataType": "Message",
                "input_field": "input_value",
                "output_field": "response",
                "input_types": ["Message", "str"],
                "output_types": ["Message"],
            },
            component_category=ComponentCategoryEnum.AGENT,
            description="Custom healthcare agent with specialized configuration",
            version="2.1.0",
            active=True,
        ),
        ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:enhanced_mcp_tool",
            base_config={
                "connection_mode": "enhanced_sse",
                "timeout_seconds": 60,
                "retry_attempts": 3,
                "health_check_interval": 30
            },
            io_mapping={
                "component": "EnhancedMCPTools",
                "dataType": "MCPTools",
                "input_field": None,
                "output_field": "response",
                "input_types": [],
                "output_types": ["DataFrame"],
            },
            component_category=ComponentCategoryEnum.TOOL,
            description="Enhanced MCP tool with improved reliability",
            version="1.5.0",
            active=True,
        ),
        # Override existing hardcoded mapping
        ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:agent",
            base_config={
                "enhanced_reasoning": True,
                "context_window": 32000,
                "streaming": True
            },
            io_mapping={
                "component": "EnhancedAgent",
                "dataType": "Message",
                "input_field": "input_value",
                "output_field": "response",
                "input_types": ["Message", "str"],
                "output_types": ["Message"],
            },
            component_category=ComponentCategoryEnum.AGENT,
            description="Enhanced agent with improved capabilities",
            version="3.0.0",
            active=True,
        ),
    ]


class TestEndToEndPrioritySystem:
    """End-to-end integration tests for the priority system."""

    @pytest.mark.asyncio
    async def test_full_spec_conversion_with_database_override(self, spec_service, mock_session, real_database_mappings):
        """Test complete specification conversion with database overrides."""
        test_spec = """
        name: Healthcare Agent Workflow
        description: A healthcare workflow with custom components
        agentGoal: Process patient data and provide insights
        components:
          input:
            type: genesis:chat_input
          custom_agent:
            type: genesis:custom_agent
            config:
              specialized_field: "cardiology"
            provides:
              - useAs: input
                in: output
          enhanced_tool:
            type: genesis:enhanced_mcp_tool
            asTools: true
            provides:
              - useAs: tools
                in: custom_agent
          standard_agent:
            type: genesis:agent
            provides:
              - useAs: input
                in: output
          output:
            type: genesis:chat_output
        """

        # Mock the mapping service to return our test mappings
        mock_service = AsyncMock()
        mock_service.get_all_component_mappings.return_value = real_database_mappings

        with patch.object(spec_service.mapper, '_get_component_mapping_service', return_value=mock_service):
            with patch.object(spec_service.converter, 'convert') as mock_convert:
                mock_convert.return_value = {"converted": True, "components": []}

                # Convert with database session
                result = await spec_service.convert_spec_to_flow(test_spec, session=mock_session)

                # Verify cache was populated
                cache_status = spec_service.mapper.get_cache_status()
                assert cache_status["cached_mappings"] == 3

                # Verify database mappings are used
                custom_agent_result = spec_service.mapper.map_component("genesis:custom_agent")
                assert custom_agent_result["component"] == "CustomHealthcareAgent"
                assert custom_agent_result["config"]["custom_system_prompt"] == "You are a specialized healthcare agent."

                enhanced_tool_result = spec_service.mapper.map_component("genesis:enhanced_mcp_tool")
                assert enhanced_tool_result["component"] == "EnhancedMCPTools"

                # Verify override of hardcoded mapping
                standard_agent_result = spec_service.mapper.map_component("genesis:agent")
                assert standard_agent_result["component"] == "EnhancedAgent"  # Database override
                assert standard_agent_result["config"]["enhanced_reasoning"] is True

                # Verify mapping sources
                assert spec_service.mapper.get_mapping_source("genesis:custom_agent") == "database_cached"
                assert spec_service.mapper.get_mapping_source("genesis:enhanced_mcp_tool") == "database_cached"
                assert spec_service.mapper.get_mapping_source("genesis:agent") == "database_cached"

    @pytest.mark.asyncio
    async def test_partial_database_availability(self, spec_service, mock_session):
        """Test behavior when database is partially available."""
        # Simulate database returning some mappings but failing for others
        partial_mappings = [
            ComponentMapping(
                id=uuid4(),
                genesis_type="genesis:working_component",
                base_config={"status": "working"},
                io_mapping={"component": "WorkingComponent"},
                component_category=ComponentCategoryEnum.TOOL,
                description="Working component",
                version="1.0.0",
                active=True,
            )
        ]

        mock_service = AsyncMock()
        mock_service.get_all_component_mappings.return_value = partial_mappings

        with patch.object(spec_service.mapper, '_get_component_mapping_service', return_value=mock_service):
            # Populate cache
            await spec_service._ensure_database_cache_populated(mock_session)

            # Test working database mapping
            working_result = spec_service.mapper.map_component("genesis:working_component")
            assert working_result["component"] == "WorkingComponent"
            assert spec_service.mapper.get_mapping_source("genesis:working_component") == "database_cached"

            # Test fallback to hardcoded for non-database components
            hardcoded_result = spec_service.mapper.map_component("genesis:agent")
            assert hardcoded_result["component"] == "Agent"  # Hardcoded fallback
            assert spec_service.mapper.get_mapping_source("genesis:agent") == "hardcoded_standard"

    @pytest.mark.asyncio
    async def test_database_connection_failure_graceful_fallback(self, spec_service, mock_session):
        """Test graceful fallback when database connection fails."""
        test_spec = """
        name: Fallback Test
        description: Test fallback behavior
        agentGoal: Test graceful degradation
        components:
          input:
            type: genesis:chat_input
          agent:
            type: genesis:agent
            provides:
              - useAs: input
                in: output
          output:
            type: genesis:chat_output
        """

        # Mock database service to fail
        mock_service = AsyncMock()
        mock_service.get_all_component_mappings.side_effect = Exception("Database connection failed")

        with patch.object(spec_service.mapper, '_get_component_mapping_service', return_value=mock_service):
            with patch.object(spec_service.converter, 'convert') as mock_convert:
                mock_convert.return_value = {"converted": True, "fallback_used": True}

                # Should not raise exception, should use hardcoded fallbacks
                result = await spec_service.convert_spec_to_flow(test_spec, session=mock_session)

                assert result["converted"] is True

                # Verify hardcoded mappings still work
                agent_result = spec_service.mapper.map_component("genesis:agent")
                assert agent_result["component"] == "Agent"
                assert spec_service.mapper.get_mapping_source("genesis:agent") == "hardcoded_standard"

    @pytest.mark.asyncio
    async def test_cache_invalidation_and_refresh(self, spec_service, mock_session):
        """Test cache invalidation and refresh scenarios."""
        initial_mappings = [
            ComponentMapping(
                id=uuid4(),
                genesis_type="genesis:versioned_component",
                base_config={"version": "1.0"},
                io_mapping={"component": "VersionedComponentV1"},
                component_category=ComponentCategoryEnum.TOOL,
                description="Version 1.0",
                version="1.0.0",
                active=True,
            )
        ]

        updated_mappings = [
            ComponentMapping(
                id=uuid4(),
                genesis_type="genesis:versioned_component",
                base_config={"version": "2.0", "new_feature": True},
                io_mapping={"component": "VersionedComponentV2"},
                component_category=ComponentCategoryEnum.TOOL,
                description="Version 2.0",
                version="2.0.0",
                active=True,
            )
        ]

        mock_service = AsyncMock()

        # First call returns initial mappings
        mock_service.get_all_component_mappings.return_value = initial_mappings

        with patch.object(spec_service.mapper, '_get_component_mapping_service', return_value=mock_service):
            # Initial cache population
            await spec_service._ensure_database_cache_populated(mock_session)

            # Verify initial mapping
            result = spec_service.mapper.map_component("genesis:versioned_component")
            assert result["component"] == "VersionedComponentV1"
            assert result["config"]["version"] == "1.0"

            # Update mock to return new mappings
            mock_service.get_all_component_mappings.return_value = updated_mappings

            # Force cache refresh
            await spec_service.mapper.refresh_cache_from_database(mock_session)

            # Verify updated mapping
            result = spec_service.mapper.map_component("genesis:versioned_component")
            assert result["component"] == "VersionedComponentV2"
            assert result["config"]["version"] == "2.0"
            assert result["config"]["new_feature"] is True


class TestConcurrentAccessAndThreadSafety:
    """Test concurrent access and thread safety."""

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self, component_mapper, mock_session):
        """Test concurrent cache operations don't interfere with each other."""
        async def populate_cache_task(task_id):
            mappings = {
                f"genesis:concurrent_component_{task_id}": {
                    "component": f"ConcurrentComponent{task_id}",
                    "config": {"task_id": task_id}
                }
            }
            component_mapper.populate_mapping_cache(mappings)
            return task_id

        # Run multiple concurrent cache operations
        tasks = [populate_cache_task(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # Verify all operations completed
        assert len(results) == 10

        # Verify all mappings are accessible
        for i in range(10):
            result = component_mapper._get_mapping_from_database(f"genesis:concurrent_component_{i}")
            assert result is not None
            assert result["component"] == f"ConcurrentComponent{i}"

    @pytest.mark.asyncio
    async def test_cache_refresh_during_mapping_operations(self, component_mapper, mock_session):
        """Test cache refresh while mapping operations are ongoing."""
        # Initial cache setup
        initial_mappings = {
            "genesis:test_component": {
                "component": "InitialComponent",
                "config": {"status": "initial"}
            }
        }
        component_mapper.populate_mapping_cache(initial_mappings)

        # Mock service for refresh
        mock_service = AsyncMock()
        mock_service.get_all_component_mappings.return_value = [
            Mock(
                genesis_type="genesis:test_component",
                base_config={"status": "refreshed"},
                io_mapping={"component": "RefreshedComponent"},
                id=uuid4()
            )
        ]

        async def mapping_operation():
            """Perform mapping operations repeatedly."""
            for _ in range(100):
                result = component_mapper.map_component("genesis:test_component")
                assert "component" in result
                await asyncio.sleep(0.001)  # Small delay to allow interleaving

        async def refresh_operation():
            """Perform cache refresh."""
            await asyncio.sleep(0.05)  # Let some mapping operations start
            with patch.object(component_mapper, '_get_component_mapping_service', return_value=mock_service):
                await component_mapper.refresh_cache_from_database(mock_session)

        # Run both operations concurrently
        await asyncio.gather(mapping_operation(), refresh_operation())

        # Verify final state
        final_result = component_mapper.map_component("genesis:test_component")
        assert final_result["component"] == "RefreshedComponent"


class TestPerformanceIntegration:
    """Integration tests for performance requirements."""

    @pytest.mark.asyncio
    async def test_large_scale_conversion_performance(self, spec_service, mock_session):
        """Test performance with large-scale specifications."""
        # Create a large specification with many components
        components_section = ""
        for i in range(50):
            components_section += f"""
          component_{i}:
            type: genesis:agent
            config:
              component_id: {i}
            provides:
              - useAs: input
                in: output
        """

        large_spec = f"""
        name: Large Scale Test
        description: Performance test with many components
        agentGoal: Test performance at scale
        components:
          input:
            type: genesis:chat_input
          {components_section}
          output:
            type: genesis:chat_output
        """

        # Create database mappings for performance test
        mock_mappings = [
            Mock(
                genesis_type="genesis:agent",
                base_config={"performance_test": True},
                io_mapping={"component": "PerformanceAgent"},
                id=uuid4()
            )
        ]

        mock_service = AsyncMock()
        mock_service.get_all_component_mappings.return_value = mock_mappings

        with patch.object(spec_service.mapper, '_get_component_mapping_service', return_value=mock_service):
            with patch.object(spec_service.converter, 'convert') as mock_convert:
                mock_convert.return_value = {"performance_test": True}

                import time
                start_time = time.time()

                result = await spec_service.convert_spec_to_flow(large_spec, session=mock_session)

                conversion_time = time.time() - start_time

                # Should complete within reasonable time (adjust based on requirements)
                assert conversion_time < 5.0  # 5 seconds for large spec
                assert result["performance_test"] is True

    def test_cache_lookup_performance_with_many_mappings(self, component_mapper):
        """Test cache lookup performance with many cached mappings."""
        # Create large cache
        large_cache = {
            f"genesis:perf_component_{i}": {
                "component": f"PerfComponent{i}",
                "config": {"index": i}
            }
            for i in range(1000)
        }

        component_mapper.populate_mapping_cache(large_cache)

        import time

        # Test lookup performance
        start_time = time.time()
        for i in range(100):
            result = component_mapper.map_component(f"genesis:perf_component_{i}")
            assert result["component"] == f"PerfComponent{i}"
        lookup_time = time.time() - start_time

        # Should be fast even with large cache
        assert lookup_time < 0.5  # 500ms for 100 lookups with 1000 cached items


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    @pytest.mark.asyncio
    async def test_healthcare_workflow_with_custom_components(self, spec_service, mock_session):
        """Test healthcare workflow with custom database components."""
        healthcare_spec = """
        name: Patient Care Workflow
        description: Complete patient care workflow with custom healthcare components
        agentGoal: Provide comprehensive patient care coordination
        components:
          patient_input:
            type: genesis:chat_input

          eligibility_check:
            type: genesis:custom_eligibility_connector
            config:
              insurance_types: ["medicare", "medicaid", "commercial"]
              real_time_verification: true
            asTools: true

          clinical_agent:
            type: genesis:enhanced_clinical_agent
            config:
              specialization: "primary_care"
              hipaa_compliant: true
              audit_logging: true
            provides:
              - useAs: input
                in: care_coordinator

          care_coordinator:
            type: genesis:agent
            provides:
              - useAs: input
                in: patient_output

          patient_output:
            type: genesis:chat_output
        """

        # Mock healthcare-specific database mappings
        healthcare_mappings = [
            Mock(
                genesis_type="genesis:custom_eligibility_connector",
                base_config={
                    "hipaa_compliant": True,
                    "audit_logging": True,
                    "encryption": "AES-256"
                },
                io_mapping={"component": "CustomEligibilityConnector"},
                id=uuid4()
            ),
            Mock(
                genesis_type="genesis:enhanced_clinical_agent",
                base_config={
                    "clinical_knowledge_base": "latest",
                    "decision_support": True,
                    "drug_interaction_checking": True
                },
                io_mapping={"component": "EnhancedClinicalAgent"},
                id=uuid4()
            )
        ]

        mock_service = AsyncMock()
        mock_service.get_all_component_mappings.return_value = healthcare_mappings

        with patch.object(spec_service.mapper, '_get_component_mapping_service', return_value=mock_service):
            with patch.object(spec_service.converter, 'convert') as mock_convert:
                mock_convert.return_value = {"healthcare_workflow": True}

                result = await spec_service.convert_spec_to_flow(healthcare_spec, session=mock_session)

                # Verify database mappings were used
                eligibility_result = spec_service.mapper.map_component("genesis:custom_eligibility_connector")
                assert eligibility_result["component"] == "CustomEligibilityConnector"
                assert eligibility_result["config"]["hipaa_compliant"] is True

                clinical_result = spec_service.mapper.map_component("genesis:enhanced_clinical_agent")
                assert clinical_result["component"] == "EnhancedClinicalAgent"
                assert clinical_result["config"]["decision_support"] is True

    @pytest.mark.asyncio
    async def test_development_to_production_migration(self, spec_service, mock_session):
        """Test migration from development hardcoded mappings to production database mappings."""
        production_spec = """
        name: Production Agent
        description: Production-ready agent with optimized configuration
        agentGoal: Handle production workloads efficiently
        components:
          input:
            type: genesis:chat_input
          agent:
            type: genesis:agent
            provides:
              - useAs: input
                in: output
          output:
            type: genesis:chat_output
        """

        # Initially use hardcoded mappings (development)
        with patch.object(spec_service.converter, 'convert') as mock_convert:
            mock_convert.return_value = {"environment": "development"}

            dev_result = await spec_service.convert_spec_to_flow(production_spec)

            # Verify hardcoded mapping is used
            agent_result = spec_service.mapper.map_component("genesis:agent")
            assert agent_result["component"] == "Agent"  # Hardcoded
            assert spec_service.mapper.get_mapping_source("genesis:agent") == "hardcoded_standard"

        # Simulate production deployment with database mappings
        production_mappings = [
            Mock(
                genesis_type="genesis:agent",
                base_config={
                    "production_optimized": True,
                    "max_concurrent_requests": 100,
                    "cache_strategy": "redis",
                    "monitoring_enabled": True
                },
                io_mapping={"component": "ProductionAgent"},
                id=uuid4()
            )
        ]

        mock_service = AsyncMock()
        mock_service.get_all_component_mappings.return_value = production_mappings

        with patch.object(spec_service.mapper, '_get_component_mapping_service', return_value=mock_service):
            with patch.object(spec_service.converter, 'convert') as mock_convert:
                mock_convert.return_value = {"environment": "production"}

                prod_result = await spec_service.convert_spec_to_flow(production_spec, session=mock_session)

                # Verify database mapping is used (production)
                agent_result = spec_service.mapper.map_component("genesis:agent")
                assert agent_result["component"] == "ProductionAgent"  # Database override
                assert agent_result["config"]["production_optimized"] is True
                assert spec_service.mapper.get_mapping_source("genesis:agent") == "database_cached"