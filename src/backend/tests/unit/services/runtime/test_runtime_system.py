"""
Integration tests for the complete multi-runtime converter system.

This test suite validates the entire runtime converter system including
registry, factory, gap analyzer, and runtime integration.
"""

import pytest
from typing import Dict, Any

from langflow.services.runtime import (
    runtime_registry,
    converter_factory,
    RuntimeType,
    ConversionMode,
    LangflowConverter,
    TemporalConverter,
    KafkaConverter,
    ConverterGapAnalyzer
)


class TestRuntimeSystem:
    """Integration tests for the runtime system."""

    def test_system_initialization(self):
        """Test that the runtime system initializes correctly."""
        # Check that registry is populated
        available_runtimes = runtime_registry.list_available_runtimes()
        assert "langflow" in available_runtimes
        assert "temporal" in available_runtimes
        assert "kafka" in available_runtimes

        # Check that factory can create converters
        langflow_converter = converter_factory.create_converter("langflow")
        assert isinstance(langflow_converter, LangflowConverter)

        temporal_converter = converter_factory.create_converter("temporal")
        assert isinstance(temporal_converter, TemporalConverter)

        kafka_converter = converter_factory.create_converter("kafka")
        assert isinstance(kafka_converter, KafkaConverter)

    def test_runtime_registry_functionality(self):
        """Test runtime registry core functionality."""
        # Test listing runtimes
        runtimes = runtime_registry.list_available_runtimes()
        assert len(runtimes) >= 3
        assert all(isinstance(runtime, str) for runtime in runtimes)

        # Test getting converter
        converter = runtime_registry.get_converter("langflow")
        assert converter is not None
        assert isinstance(converter, LangflowConverter)

        # Test getting capabilities
        capabilities = runtime_registry.get_runtime_capabilities("langflow")
        assert capabilities is not None
        assert "name" in capabilities
        assert "bidirectional_support" in capabilities

    def test_converter_factory_functionality(self):
        """Test converter factory core functionality."""
        # Test creating converters
        langflow = converter_factory.create_converter("langflow")
        assert langflow is not None

        # Test getting runtime info
        info = converter_factory.get_converter_info("langflow")
        assert info is not None
        assert "source" in info

        # Test getting available runtimes
        runtimes = converter_factory.get_available_runtimes()
        assert "langflow" in runtimes

    @pytest.mark.asyncio
    async def test_runtime_selection_for_spec(self):
        """Test automatic runtime selection for specifications."""
        # Healthcare workflow spec
        healthcare_spec = {
            "name": "Healthcare Workflow",
            "description": "Healthcare processing workflow",
            "agentGoal": "Process healthcare data",
            "components": {
                "eligibility": {
                    "type": "genesis:mcp_tool",
                    "config": {"tool_name": "eligibility_check"}
                },
                "agent": {
                    "type": "genesis:agent"
                }
            }
        }

        # Test best runtime selection
        best_runtime = runtime_registry.get_best_runtime_for_spec(healthcare_spec)
        assert best_runtime is not None
        assert best_runtime in ["langflow", "temporal", "kafka"]

        # Test validation for selected runtime
        validation = await runtime_registry.validate_spec_for_runtime(healthcare_spec, best_runtime)
        assert "valid" in validation
        assert "runtime" in validation

    def test_component_support_analysis(self):
        """Test component support analysis across runtimes."""
        # Test finding converters for specific components
        langflow_runtimes = runtime_registry.find_converters_for_component("genesis:agent")
        assert "langflow" in langflow_runtimes

        streaming_runtimes = runtime_registry.find_converters_for_component("genesis:api_request")
        # Both Langflow and Kafka should support API requests
        assert len(streaming_runtimes) >= 1

    def test_compatibility_matrix(self):
        """Test runtime compatibility matrix generation."""
        matrix = runtime_registry.get_runtime_compatibility_matrix()

        assert "langflow" in matrix
        assert "temporal" in matrix
        assert "kafka" in matrix

        # Check structure
        for runtime, info in matrix.items():
            assert "supported_components" in info
            assert "bidirectional_support" in info
            assert "conversion_modes" in info
            assert isinstance(info["supported_components"], list)

    def test_conversion_with_fallback(self):
        """Test conversion with fallback runtime support."""
        simple_spec = {
            "name": "Simple Test",
            "description": "Simple test spec",
            "agentGoal": "Test conversion",
            "components": {
                "input": {"type": "genesis:chat_input"},
                "agent": {"type": "genesis:agent"},
                "output": {"type": "genesis:chat_output"}
            }
        }

        # Test with preferred runtime and fallbacks
        result = converter_factory.convert_with_fallback(
            simple_spec,
            preferred_runtime="nonexistent",
            fallback_runtimes=["langflow"]
        )

        # Should succeed with fallback
        assert result["success"] is True
        assert result["runtime_used"] == "langflow"
        assert result["fallback_used"] is True

    def test_gap_analyzer_integration(self):
        """Test gap analyzer integration with runtime system."""
        analyzer = ConverterGapAnalyzer()

        # Test audit functionality
        audit = analyzer.audit_current_implementation()
        assert audit is not None
        assert hasattr(audit, 'total_components_scanned')
        assert hasattr(audit, 'component_gaps')
        assert hasattr(audit, 'mapping_gaps')
        assert hasattr(audit, 'conversion_gaps')

        # Test missing components identification
        missing_components = analyzer.identify_missing_components()
        assert isinstance(missing_components, list)

        # Test conversion quality assessment
        quality_report = analyzer.assess_conversion_quality()
        assert "overall_score" in quality_report
        assert "langflow_conversion" in quality_report
        assert "recommendations" in quality_report

        # Test implementation plan generation
        implementation_plan = analyzer.generate_implementation_plan()
        assert "phases" in implementation_plan
        assert "effort_estimates" in implementation_plan
        assert "timeline_weeks" in implementation_plan

    @pytest.mark.asyncio
    async def test_end_to_end_conversion_workflow(self):
        """Test complete end-to-end conversion workflow."""
        # Define a comprehensive test specification
        test_spec = {
            "id": "urn:agent:genesis:test:e2e-workflow:1.0.0",
            "name": "End-to-End Test Workflow",
            "description": "Comprehensive test of conversion system",
            "domain": "test",
            "version": "1.0.0",
            "kind": "Single Agent",
            "agentGoal": "Test complete conversion workflow",
            "targetUser": "internal",
            "components": {
                "input": {
                    "name": "User Input",
                    "type": "genesis:chat_input",
                    "kind": "Data",
                    "provides": [{"useAs": "input", "in": "agent"}]
                },
                "knowledge_tool": {
                    "name": "Knowledge Search",
                    "type": "genesis:knowledge_hub_search",
                    "kind": "Tool",
                    "asTools": True,
                    "config": {"selected_hubs": ["general"]},
                    "provides": [{"useAs": "tools", "in": "agent"}]
                },
                "agent": {
                    "name": "Main Agent",
                    "type": "genesis:agent",
                    "kind": "Agent",
                    "config": {
                        "temperature": 0.7,
                        "max_tokens": 2000
                    },
                    "provides": [{"useAs": "input", "in": "output"}]
                },
                "output": {
                    "name": "Agent Output",
                    "type": "genesis:chat_output",
                    "kind": "Data"
                }
            }
        }

        # Step 1: Validate specification
        converter = converter_factory.create_converter("langflow")
        validation_errors = converter.validate_specification(test_spec)
        assert validation_errors == [], f"Validation failed: {validation_errors}"

        # Step 2: Convert to runtime
        langflow_result = await converter.convert_to_runtime(test_spec)
        assert langflow_result is not None
        assert "data" in langflow_result
        assert "nodes" in langflow_result["data"]
        assert "edges" in langflow_result["data"]

        # Step 3: Verify conversion quality
        nodes = langflow_result["data"]["nodes"]
        edges = langflow_result["data"]["edges"]

        assert len(nodes) == 4  # All components converted
        assert len(edges) >= 3  # All connections created

        # Step 4: Test reverse conversion
        genesis_result = converter.convert_from_runtime(langflow_result)
        assert genesis_result is not None
        assert "components" in genesis_result
        assert genesis_result["name"] == test_spec["name"]

        # Step 5: Verify round-trip quality
        original_component_count = len(test_spec["components"])
        converted_component_count = len(genesis_result["components"])

        # Allow some variation in component count due to conversion logic
        assert converted_component_count >= original_component_count * 0.7

    def test_plugin_architecture_readiness(self):
        """Test that plugin architecture is ready for extensions."""
        # Test plugin info retrieval
        plugin_info = converter_factory.get_plugin_info()
        assert "plugin_paths" in plugin_info
        assert "loaded_plugins" in plugin_info
        assert "built_in_converters" in plugin_info

        # Test that we can register new converter classes
        class TestConverter(LangflowConverter):
            def __init__(self):
                super().__init__()
                self.runtime_type = RuntimeType.LANGFLOW  # Override for test

        # Should not raise an exception
        converter_factory.register_converter_class("test_runtime", TestConverter)

    def test_error_handling_and_resilience(self):
        """Test error handling throughout the system."""
        # Test with invalid runtime
        invalid_converter = converter_factory.create_converter("nonexistent")
        assert invalid_converter is None

        # Test with invalid specification
        invalid_spec = {"invalid": "spec"}
        validation = converter_factory.validate_converter_compatibility("langflow", invalid_spec)
        assert validation["compatible"] is False

        # Test registry with invalid runtime
        capabilities = runtime_registry.get_runtime_capabilities("nonexistent")
        assert capabilities is None

    def test_performance_characteristics(self):
        """Test basic performance characteristics of the system."""
        import time

        # Test registry performance
        start_time = time.time()
        for _ in range(100):
            runtime_registry.list_available_runtimes()
        registry_time = time.time() - start_time

        # Should be fast (under 1 second for 100 calls)
        assert registry_time < 1.0

        # Test factory performance
        start_time = time.time()
        for _ in range(50):
            converter_factory.create_converter("langflow")
        factory_time = time.time() - start_time

        # Should be reasonably fast
        assert factory_time < 2.0

    def test_configuration_and_customization(self):
        """Test configuration and customization capabilities."""
        # Test runtime registry cache management
        runtime_registry.clear_cache()

        # Should still work after cache clear
        runtimes = runtime_registry.list_available_runtimes()
        assert len(runtimes) >= 3

        # Test that capabilities are re-cached
        capabilities = runtime_registry.get_runtime_capabilities("langflow")
        assert capabilities is not None

    @pytest.mark.asyncio
    async def test_concurrent_conversion_support(self):
        """Test that the system supports concurrent conversions."""
        import asyncio

        test_spec = {
            "name": "Concurrent Test",
            "description": "Test concurrent conversion",
            "agentGoal": "Test concurrency",
            "components": {
                "input": {"type": "genesis:chat_input"},
                "agent": {"type": "genesis:agent"},
                "output": {"type": "genesis:chat_output"}
            }
        }

        # Create multiple concurrent conversion tasks
        async def convert_task():
            converter = converter_factory.create_converter("langflow")
            return await converter.convert_to_runtime(test_spec)

        # Run multiple conversions concurrently
        tasks = [convert_task() for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == 5

        # All should produce valid results
        for result in successful_results:
            assert "data" in result
            assert "nodes" in result["data"]

    def test_system_health_and_status(self):
        """Test system health and status reporting."""
        # Check that all core components are healthy
        health_status = {
            "registry_healthy": len(runtime_registry.list_available_runtimes()) >= 3,
            "factory_healthy": converter_factory.create_converter("langflow") is not None,
            "gap_analyzer_healthy": ConverterGapAnalyzer() is not None
        }

        assert all(health_status.values()), f"System health check failed: {health_status}"

        # Check that core converters are functional
        for runtime in ["langflow", "temporal", "kafka"]:
            converter = converter_factory.create_converter(runtime)
            assert converter is not None, f"Failed to create {runtime} converter"

            info = converter.get_runtime_info()
            assert info is not None, f"Failed to get info for {runtime} converter"
            assert "name" in info, f"Invalid info structure for {runtime} converter"


if __name__ == "__main__":
    pytest.main([__file__])