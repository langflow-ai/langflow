"""
Unit tests for Phase 3: Conversion Architecture Enhancement.

This module tests the enhanced converter architecture including:
- Pluggable converter system with runtime adapters
- Enhanced type compatibility validation with pre-conversion checking
- Comprehensive edge validation and connection rules
- Performance optimization capabilities
"""

import pytest
import asyncio
from typing import Dict, Any, List
from unittest.mock import Mock, patch

from .base_converter import (
    RuntimeConverter,
    RuntimeType,
    ConversionResult,
    ValidationOptions,
    ComponentCompatibility,
    EdgeValidationResult
)
from .converter_factory import ConverterFactory, ConverterRegistry
from .langflow_converter import LangflowConverter
from .performance_optimizer import PerformanceOptimizer, OptimizationLevel


class TestRuntimeConverter:
    """Test the base RuntimeConverter interface."""

    @pytest.fixture
    def mock_converter(self):
        """Create a mock converter for testing."""
        class MockConverter(RuntimeConverter):
            def get_runtime_info(self) -> Dict[str, Any]:
                return {
                    "name": "Mock Runtime",
                    "version": "1.0.0",
                    "runtime_type": self.runtime_type.value,
                    "capabilities": ["test"],
                    "supported_components": ["genesis:test"],
                    "bidirectional_support": False,
                    "streaming_support": True
                }

            def validate_specification(self, spec: Dict[str, Any]) -> List[str]:
                return []

            async def convert_to_runtime(self, spec: Dict[str, Any], variables=None, validation_options=None) -> ConversionResult:
                return ConversionResult(
                    success=True,
                    runtime_type=self.runtime_type,
                    flow_data={"mock": "data"},
                    metadata={"test": True}
                )

            async def convert_from_runtime(self, runtime_spec: Dict[str, Any]) -> Dict[str, Any]:
                return {"mock": "genesis_spec"}

            def supports_component_type(self, component_type: str) -> bool:
                return component_type == "genesis:test"

            def validate_component_compatibility(self, component: Dict[str, Any]) -> ComponentCompatibility:
                return ComponentCompatibility(
                    genesis_type=component.get("type", "unknown"),
                    runtime_component="MockComponent",
                    supported_inputs=["input"],
                    supported_outputs=["output"],
                    configuration_schema={},
                    constraints=[],
                    performance_hints={}
                )

            def get_runtime_constraints(self) -> Dict[str, Any]:
                return {"max_components": 10}

            async def validate_edge_connection(self, source_comp, target_comp, connection) -> EdgeValidationResult:
                return EdgeValidationResult(
                    valid=True,
                    source_component=source_comp.get("id", "source"),
                    target_component=target_comp.get("id", "target"),
                    connection_type=connection.get("useAs", "test"),
                    errors=[],
                    warnings=[],
                    suggestions=[],
                    compatibility_score=1.0
                )

        return MockConverter(RuntimeType.GENERIC)

    @pytest.mark.asyncio
    async def test_pre_conversion_validation(self, mock_converter):
        """Test pre-conversion validation functionality."""
        spec = {
            "name": "Test Spec",
            "description": "Test specification",
            "agentGoal": "Test goal",
            "components": [
                {"id": "test1", "type": "genesis:test", "config": {}},
                {"id": "test2", "type": "genesis:test", "config": {}}
            ]
        }

        validation_result = await mock_converter.pre_conversion_validation(spec)

        assert validation_result["valid"] is True
        assert isinstance(validation_result["errors"], list)
        assert isinstance(validation_result["warnings"], list)
        assert isinstance(validation_result["suggestions"], list)
        assert "validation_metadata" in validation_result

    @pytest.mark.asyncio
    async def test_optimize_for_performance(self, mock_converter):
        """Test performance optimization functionality."""
        spec = {
            "name": "Test Spec",
            "components": [
                {"id": "test1", "type": "genesis:test", "config": {"timeout": 60}}
            ]
        }

        optimization_result = await mock_converter.optimize_for_performance(spec, "fast")

        assert "spec" in optimization_result
        assert "optimizations_applied" in optimization_result
        assert "optimization_metadata" in optimization_result

    def test_performance_mode_setting(self, mock_converter):
        """Test performance mode configuration."""
        mock_converter.set_performance_mode("thorough")
        assert mock_converter.performance_mode == "thorough"

        with pytest.raises(ValueError):
            mock_converter.set_performance_mode("invalid")


class TestConverterFactory:
    """Test the ConverterFactory functionality."""

    @pytest.fixture
    def factory(self):
        """Create a factory with clean registry."""
        registry = ConverterRegistry()
        return ConverterFactory(registry)

    @pytest.fixture
    def mock_converter_class(self):
        """Create a mock converter class."""
        class MockConverter(RuntimeConverter):
            def get_runtime_info(self):
                return {"name": "Mock", "version": "1.0.0", "runtime_type": self.runtime_type.value}

            def validate_specification(self, spec):
                return []

            async def convert_to_runtime(self, spec, variables=None, validation_options=None):
                return ConversionResult(True, self.runtime_type, {"mock": "data"})

            async def convert_from_runtime(self, runtime_spec):
                return {"mock": "spec"}

            def supports_component_type(self, component_type):
                return True

            def validate_component_compatibility(self, component):
                return ComponentCompatibility("test", "MockComponent", [], [], {}, [], {})

            def get_runtime_constraints(self):
                return {}

            async def validate_edge_connection(self, source_comp, target_comp, connection):
                return EdgeValidationResult(True, "source", "target", "test", [], [], [], 1.0)

        return MockConverter

    def test_register_converter(self, factory, mock_converter_class):
        """Test converter registration."""
        factory.registry.register_converter(
            RuntimeType.GENERIC,
            mock_converter_class,
            {"test": True}
        )

        available_runtimes = factory.registry.get_available_runtimes()
        assert RuntimeType.GENERIC in available_runtimes

        converter = factory.registry.get_converter(RuntimeType.GENERIC)
        assert isinstance(converter, mock_converter_class)

    def test_get_unsupported_converter(self, factory):
        """Test error handling for unsupported runtime."""
        with pytest.raises(ValueError, match="Unsupported runtime type"):
            factory.registry.get_converter(RuntimeType.TEMPORAL)

    @pytest.mark.asyncio
    async def test_convert_specification(self, factory, mock_converter_class):
        """Test specification conversion through factory."""
        factory.registry.register_converter(RuntimeType.GENERIC, mock_converter_class)

        spec = {"name": "Test", "components": []}
        result = await factory.convert_specification(spec, RuntimeType.GENERIC)

        assert result.success is True
        assert result.runtime_type == RuntimeType.GENERIC
        assert "factory_metadata" in result.metadata

    @pytest.mark.asyncio
    async def test_validate_specification(self, factory, mock_converter_class):
        """Test specification validation through factory."""
        factory.registry.register_converter(RuntimeType.GENERIC, mock_converter_class)

        spec = {"name": "Test", "components": []}
        result = await factory.validate_specification(spec, RuntimeType.GENERIC)

        assert isinstance(result, dict)
        assert "valid" in result


class TestLangflowConverter:
    """Test the LangflowConverter implementation."""

    @pytest.fixture
    def converter(self):
        """Create a LangflowConverter instance."""
        return LangflowConverter()

    def test_runtime_info(self, converter):
        """Test runtime info retrieval."""
        info = converter.get_runtime_info()

        assert info["name"] == "Langflow"
        assert info["runtime_type"] == "langflow"
        assert "capabilities" in info
        assert "validation_features" in info
        assert info["bidirectional_support"] is True

    def test_supports_component_type(self, converter):
        """Test component type support checking."""
        # Test with known component types
        assert converter.supports_component_type("genesis:agent") is True
        assert converter.supports_component_type("genesis:chat_input") is True

        # Test with unknown component type
        assert converter.supports_component_type("genesis:unknown") is False

    def test_get_supported_components(self, converter):
        """Test supported components retrieval."""
        supported = converter.get_supported_components()

        assert isinstance(supported, set)
        assert len(supported) > 0
        assert "genesis:agent" in supported
        assert "genesis:chat_input" in supported

    def test_get_runtime_constraints(self, converter):
        """Test runtime constraints retrieval."""
        constraints = converter.get_runtime_constraints()

        assert isinstance(constraints, dict)
        assert "max_components" in constraints
        assert "max_memory_mb" in constraints
        assert "component_limits" in constraints

    def test_validate_component_compatibility(self, converter):
        """Test component compatibility validation."""
        component = {
            "id": "test-agent",
            "type": "genesis:agent",
            "config": {"temperature": 0.7}
        }

        compatibility = converter.validate_component_compatibility(component)

        assert compatibility.genesis_type == "genesis:agent"
        assert isinstance(compatibility.runtime_component, str)
        assert isinstance(compatibility.supported_inputs, list)
        assert isinstance(compatibility.supported_outputs, list)

    @pytest.mark.asyncio
    async def test_validate_edge_connection(self, converter):
        """Test edge connection validation."""
        source_comp = {
            "id": "input",
            "type": "genesis:chat_input",
            "asTools": False
        }
        target_comp = {
            "id": "agent",
            "type": "genesis:agent"
        }
        connection = {
            "useAs": "input",
            "in": "agent"
        }

        result = await converter.validate_edge_connection(source_comp, target_comp, connection)

        assert isinstance(result, EdgeValidationResult)
        assert result.source_component == "input"
        assert result.target_component == "agent"
        assert result.connection_type == "input"

    @pytest.mark.asyncio
    async def test_convert_to_runtime_basic(self, converter):
        """Test basic conversion to runtime."""
        spec = {
            "name": "Test Agent",
            "description": "Test specification",
            "agentGoal": "Test goal",
            "components": [
                {
                    "id": "input",
                    "type": "genesis:chat_input",
                    "config": {}
                },
                {
                    "id": "agent",
                    "type": "genesis:agent",
                    "config": {"temperature": 0.7}
                }
            ]
        }

        with patch.object(converter.flow_converter, 'convert') as mock_convert:
            mock_convert.return_value = {"id": "test-flow", "data": {"nodes": [], "edges": []}}

            result = await converter.convert_to_runtime(spec)

            assert result.success is True
            assert result.runtime_type == RuntimeType.LANGFLOW
            assert "langflow_metadata" in result.metadata
            assert "conversion_duration_seconds" in result.performance_metrics

    def test_clear_cache(self, converter):
        """Test cache clearing functionality."""
        # Populate cache
        _ = converter.get_supported_components()
        assert converter._supported_components_cache is not None

        # Clear cache
        converter.clear_cache()
        assert converter._supported_components_cache is None


class TestPhase3Integration:
    """Integration tests for Phase 3 architecture."""

    @pytest.mark.asyncio
    async def test_end_to_end_validation(self):
        """Test end-to-end validation flow."""
        from . import converter_factory, RuntimeType, ValidationOptions

        spec = {
            "name": "Integration Test",
            "description": "End-to-end test specification",
            "agentGoal": "Test complete validation flow",
            "components": [
                {
                    "id": "input",
                    "type": "genesis:chat_input",
                    "config": {}
                },
                {
                    "id": "agent",
                    "type": "genesis:agent",
                    "config": {"temperature": 0.7},
                    "provides": [{"useAs": "output", "in": "output"}]
                },
                {
                    "id": "output",
                    "type": "genesis:chat_output",
                    "config": {}
                }
            ]
        }

        validation_options = ValidationOptions(
            enable_type_checking=True,
            enable_performance_hints=True,
            enable_edge_validation=True
        )

        result = await converter_factory.validate_specification(
            spec, RuntimeType.LANGFLOW, validation_options
        )

        assert isinstance(result, dict)
        assert "valid" in result
        assert "validation_metadata" in result

    @pytest.mark.asyncio
    async def test_multi_runtime_compatibility(self):
        """Test multi-runtime compatibility checking."""
        from . import converter_factory

        spec = {
            "name": "Multi-Runtime Test",
            "description": "Test multi-runtime compatibility",
            "agentGoal": "Test compatibility across runtimes",
            "components": [
                {"id": "input", "type": "genesis:chat_input"},
                {"id": "agent", "type": "genesis:agent"}
            ]
        }

        # Only test with Langflow since other runtimes aren't fully implemented
        compatibility_results = await converter_factory.check_runtime_compatibility(
            spec, [RuntimeType.LANGFLOW]
        )

        assert isinstance(compatibility_results, dict)
        assert RuntimeType.LANGFLOW in compatibility_results

    @pytest.mark.asyncio
    async def test_performance_optimization(self):
        """Test performance optimization features."""
        from . import converter_factory, RuntimeType

        spec = {
            "name": "Performance Test",
            "components": [
                {
                    "id": "agent",
                    "type": "genesis:agent",
                    "config": {"temperature": 0.9, "timeout": 120, "max_tokens": 4000}
                }
            ]
        }

        optimization_result = await converter_factory.optimize_specification(
            spec, RuntimeType.LANGFLOW, "thorough"
        )

        assert "spec" in optimization_result
        assert "optimizations_applied" in optimization_result
        assert "optimization_metadata" in optimization_result


class TestPerformanceOptimizer:
    """Test the PerformanceOptimizer functionality."""

    @pytest.fixture
    def optimizer(self):
        """Create a PerformanceOptimizer instance."""
        return PerformanceOptimizer()

    @pytest.fixture
    def sample_spec(self):
        """Create a sample specification for testing."""
        return {
            "name": "Performance Test",
            "description": "Test specification for performance optimization",
            "agentGoal": "Test performance optimization features",
            "components": [
                {
                    "id": "input",
                    "type": "genesis:chat_input",
                    "config": {}
                },
                {
                    "id": "agent",
                    "type": "genesis:agent",
                    "config": {
                        "temperature": 0.9,
                        "timeout": 120,
                        "max_tokens": 4000
                    }
                },
                {
                    "id": "tool",
                    "type": "genesis:knowledge_hub_search",
                    "config": {
                        "timeout": 60
                    },
                    "asTools": True,
                    "provides": [{"useAs": "tools", "in": "agent"}]
                },
                {
                    "id": "output",
                    "type": "genesis:chat_output",
                    "config": {}
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_optimize_specification(self, optimizer, sample_spec):
        """Test specification optimization."""
        result = await optimizer.optimize_specification(
            sample_spec, RuntimeType.LANGFLOW, OptimizationLevel.BALANCED
        )

        assert result["success"] is True
        assert "optimized_spec" in result
        assert "performance_metrics" in result
        assert "optimizations_applied" in result

        # Check that optimizations were applied
        optimized_spec = result["optimized_spec"]
        agent_config = None
        for comp in optimizer._get_components_list(optimized_spec):
            if comp.get("id") == "agent":
                agent_config = comp.get("config", {})
                break

        assert agent_config is not None

    @pytest.mark.asyncio
    async def test_benchmark_conversion_performance(self, optimizer, sample_spec):
        """Test conversion performance benchmarking."""
        result = await optimizer.benchmark_conversion_performance(
            sample_spec, [RuntimeType.LANGFLOW], iterations=1
        )

        assert "benchmark_results" in result
        assert "fastest_runtime" in result
        assert "most_reliable_runtime" in result

        langflow_results = result["benchmark_results"].get("langflow")
        assert langflow_results is not None
        assert "avg_duration_seconds" in langflow_results

    @pytest.mark.asyncio
    async def test_detect_performance_bottlenecks(self, optimizer, sample_spec):
        """Test performance bottleneck detection."""
        result = await optimizer.detect_performance_bottlenecks(
            sample_spec, RuntimeType.LANGFLOW
        )

        assert "bottlenecks_detected" in result
        assert "recommendations" in result
        assert "severity_summary" in result
        assert "analysis_metadata" in result

    def test_get_optimization_recommendations(self, optimizer):
        """Test optimization recommendation generation."""
        from .performance_optimizer import PerformanceMetrics

        metrics = PerformanceMetrics(
            conversion_duration_seconds=15.0,
            validation_duration_seconds=2.0,
            component_count=10,
            edge_count=15,
            memory_estimate_mb=1500,
            complexity_score=7.0,
            optimization_level="fast",
            optimizations_applied=["reduce_timeouts"],
            bottlenecks_detected=[],
            recommendations=[]
        )

        recommendations = optimizer.get_optimization_recommendations(metrics)

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

        # Should recommend improvements based on metrics
        assert any("conversion" in rec.lower() for rec in recommendations)
        assert any("memory" in rec.lower() for rec in recommendations)

    def test_optimization_rules_initialization(self, optimizer):
        """Test that optimization rules are properly initialized."""
        assert len(optimizer.optimization_rules) > 0

        # Check that rules have required attributes
        for rule in optimizer.optimization_rules:
            assert hasattr(rule, "name")
            assert hasattr(rule, "description")
            assert hasattr(rule, "condition")
            assert hasattr(rule, "optimization")
            assert hasattr(rule, "priority")
            assert hasattr(rule, "runtime_types")

    def test_complexity_estimation(self, optimizer, sample_spec):
        """Test complexity estimation."""
        complexity = optimizer._estimate_complexity(sample_spec)

        assert isinstance(complexity, float)
        assert 0.0 <= complexity <= 10.0

        # More components should increase complexity
        extended_spec = sample_spec.copy()
        extended_spec["components"] = sample_spec["components"] * 3  # Triple components
        extended_complexity = optimizer._estimate_complexity(extended_spec)

        assert extended_complexity > complexity

    def test_memory_estimation(self, optimizer, sample_spec):
        """Test memory usage estimation."""
        memory_estimate = optimizer._estimate_memory_usage(sample_spec)

        assert isinstance(memory_estimate, int)
        assert memory_estimate > 0

        # Should be reasonable for small specification
        assert 100 <= memory_estimate <= 1000

    @pytest.mark.asyncio
    async def test_optimization_level_effects(self, optimizer, sample_spec):
        """Test that different optimization levels produce different results."""
        # Test fast optimization
        fast_result = await optimizer.optimize_specification(
            sample_spec, RuntimeType.LANGFLOW, OptimizationLevel.FAST
        )

        # Test thorough optimization
        thorough_result = await optimizer.optimize_specification(
            sample_spec, RuntimeType.LANGFLOW, OptimizationLevel.THOROUGH
        )

        assert fast_result["success"] is True
        assert thorough_result["success"] is True

        # Thorough should typically apply more optimizations
        fast_optimizations = len(fast_result["optimizations_applied"])
        thorough_optimizations = len(thorough_result["optimizations_applied"])

        # Note: This assertion might not always hold depending on the spec,
        # but generally thorough mode should do more work
        assert thorough_optimizations >= fast_optimizations

    def test_performance_history_recording(self, optimizer):
        """Test performance history recording."""
        from .performance_optimizer import PerformanceMetrics

        initial_history_length = len(optimizer.performance_history)

        metrics = PerformanceMetrics(
            conversion_duration_seconds=1.0,
            validation_duration_seconds=0.5,
            component_count=5,
            edge_count=10,
            memory_estimate_mb=200,
            complexity_score=2.0,
            optimization_level="balanced",
            optimizations_applied=["test_optimization"],
            bottlenecks_detected=[],
            recommendations=[]
        )

        optimizer._record_performance_history(metrics, RuntimeType.LANGFLOW)

        assert len(optimizer.performance_history) == initial_history_length + 1

        # Test history entry format
        latest_entry = optimizer.performance_history[-1]
        assert "timestamp" in latest_entry
        assert "runtime_type" in latest_entry
        assert "metrics" in latest_entry
        assert latest_entry["runtime_type"] == "langflow"


class TestPhase3IntegrationComplete:
    """Complete integration tests for Phase 3 architecture."""

    @pytest.mark.asyncio
    async def test_complete_workflow_with_optimization(self):
        """Test complete workflow including optimization and performance monitoring."""
        from . import converter_factory, RuntimeType, ValidationOptions
        from .performance_optimizer import performance_optimizer

        spec = {
            "name": "Complete Integration Test",
            "description": "End-to-end test with optimization",
            "agentGoal": "Test complete Phase 3 workflow",
            "components": [
                {
                    "id": "input",
                    "type": "genesis:chat_input",
                    "config": {}
                },
                {
                    "id": "agent",
                    "type": "genesis:agent",
                    "config": {
                        "temperature": 0.9,
                        "timeout": 180,
                        "max_tokens": 5000
                    },
                    "provides": [{"useAs": "output", "in": "output"}]
                },
                {
                    "id": "output",
                    "type": "genesis:chat_output",
                    "config": {}
                }
            ]
        }

        # Step 1: Performance analysis and optimization
        optimization_result = await performance_optimizer.optimize_specification(
            spec, RuntimeType.LANGFLOW, OptimizationLevel.BALANCED
        )

        assert optimization_result["success"] is True
        optimized_spec = optimization_result["optimized_spec"]

        # Step 2: Enhanced validation
        validation_options = ValidationOptions(
            enable_type_checking=True,
            enable_performance_hints=True,
            enable_edge_validation=True
        )

        validation_result = await converter_factory.validate_specification(
            optimized_spec, RuntimeType.LANGFLOW, validation_options
        )

        assert "valid" in validation_result

        # Step 3: Performance benchmarking
        benchmark_result = await performance_optimizer.benchmark_conversion_performance(
            optimized_spec, [RuntimeType.LANGFLOW], iterations=1
        )

        assert "benchmark_results" in benchmark_result

        # Step 4: Bottleneck detection
        bottleneck_result = await performance_optimizer.detect_performance_bottlenecks(
            optimized_spec, RuntimeType.LANGFLOW
        )

        assert "bottlenecks_detected" in bottleneck_result

    @pytest.mark.asyncio
    async def test_multi_runtime_comparison(self):
        """Test multi-runtime comparison capabilities."""
        from . import converter_factory

        spec = {
            "name": "Multi-Runtime Test",
            "description": "Test multi-runtime capabilities",
            "agentGoal": "Compare runtime performance",
            "components": [
                {"id": "input", "type": "genesis:chat_input"},
                {"id": "agent", "type": "genesis:agent"},
                {"id": "output", "type": "genesis:chat_output"}
            ]
        }

        # Test with multiple runtimes (including skeleton implementations)
        compatibility_results = await converter_factory.check_runtime_compatibility(
            spec, [RuntimeType.LANGFLOW, RuntimeType.TEMPORAL]
        )

        assert isinstance(compatibility_results, dict)
        assert len(compatibility_results) >= 2

        # Langflow should be compatible
        assert RuntimeType.LANGFLOW in compatibility_results
        langflow_result = compatibility_results[RuntimeType.LANGFLOW]
        assert "compatible" in langflow_result

        # Temporal should report skeleton status
        assert RuntimeType.TEMPORAL in compatibility_results
        temporal_result = compatibility_results[RuntimeType.TEMPORAL]
        assert "compatible" in temporal_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])