"""
Performance Optimization Service for Phase 3 Converters.

This module provides advanced performance optimization capabilities for
Genesis specification conversion, focusing on:
- Conversion performance and reliability
- Memory usage optimization
- Component execution efficiency
- Workflow optimization patterns
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from .base_converter import RuntimeType, ValidationOptions
from .converter_factory import converter_factory

logger = logging.getLogger(__name__)


class OptimizationLevel(Enum):
    """Optimization levels for performance tuning."""
    FAST = "fast"
    BALANCED = "balanced"
    THOROUGH = "thorough"
    CUSTOM = "custom"


@dataclass
class PerformanceMetrics:
    """Performance metrics for conversion operations."""
    conversion_duration_seconds: float
    validation_duration_seconds: float
    component_count: int
    edge_count: int
    memory_estimate_mb: int
    complexity_score: float
    optimization_level: str
    optimizations_applied: List[str]
    bottlenecks_detected: List[str]
    recommendations: List[str]


@dataclass
class OptimizationRule:
    """Performance optimization rule definition."""
    name: str
    description: str
    condition: callable
    optimization: callable
    priority: int  # 1-10, higher is more important
    runtime_types: List[RuntimeType]


class PerformanceOptimizer:
    """
    Advanced performance optimizer for Genesis specification conversion.

    Provides comprehensive performance optimization including:
    - Automatic bottleneck detection
    - Intelligent optimization rule application
    - Performance monitoring and metrics
    - Conversion reliability enhancement
    """

    def __init__(self):
        """Initialize the performance optimizer."""
        self.optimization_rules = self._initialize_optimization_rules()
        self.performance_history = []
        self.optimization_cache = {}

    async def optimize_specification(self,
                                   spec_dict: Dict[str, Any],
                                   target_runtime: RuntimeType,
                                   optimization_level: OptimizationLevel = OptimizationLevel.BALANCED,
                                   custom_rules: Optional[List[OptimizationRule]] = None) -> Dict[str, Any]:
        """
        Optimize Genesis specification for performance.

        Args:
            spec_dict: Genesis specification dictionary
            target_runtime: Target runtime type
            optimization_level: Optimization level
            custom_rules: Custom optimization rules

        Returns:
            Optimization result with metrics and optimized spec
        """
        optimization_start = datetime.utcnow()

        try:
            # Get converter for runtime
            converter = converter_factory.registry.get_converter(target_runtime)

            # Analyze current specification
            analysis_result = await self._analyze_specification_performance(
                spec_dict, converter
            )

            # Apply optimization rules
            optimized_spec, applied_optimizations = await self._apply_optimization_rules(
                spec_dict, converter, optimization_level, custom_rules
            )

            # Validate optimizations
            validation_result = await self._validate_optimizations(
                optimized_spec, converter
            )

            # Calculate performance metrics
            optimization_duration = (datetime.utcnow() - optimization_start).total_seconds()
            metrics = self._calculate_performance_metrics(
                spec_dict, optimized_spec, optimization_duration, applied_optimizations
            )

            # Store performance history
            self._record_performance_history(metrics, target_runtime)

            return {
                "success": True,
                "optimized_spec": optimized_spec,
                "original_spec": spec_dict,
                "performance_metrics": metrics,
                "analysis_result": analysis_result,
                "validation_result": validation_result,
                "optimizations_applied": applied_optimizations,
                "optimization_metadata": {
                    "optimization_level": optimization_level.value,
                    "runtime_type": target_runtime.value,
                    "optimization_duration_seconds": optimization_duration,
                    "rules_evaluated": len(self.optimization_rules),
                    "rules_applied": len(applied_optimizations)
                }
            }

        except Exception as e:
            logger.error(f"Performance optimization failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "optimized_spec": spec_dict,  # Return original on error
                "performance_metrics": None,
                "optimization_metadata": {
                    "optimization_level": optimization_level.value,
                    "runtime_type": target_runtime.value,
                    "error": str(e)
                }
            }

    async def benchmark_conversion_performance(self,
                                             spec_dict: Dict[str, Any],
                                             runtime_types: List[RuntimeType],
                                             iterations: int = 3) -> Dict[str, Any]:
        """
        Benchmark conversion performance across multiple runtimes.

        Args:
            spec_dict: Genesis specification dictionary
            runtime_types: List of runtime types to benchmark
            iterations: Number of iterations for averaging

        Returns:
            Benchmark results with performance comparisons
        """
        benchmark_results = {}

        for runtime_type in runtime_types:
            runtime_results = []

            for i in range(iterations):
                try:
                    start_time = datetime.utcnow()

                    # Run conversion with performance monitoring
                    result = await converter_factory.convert_specification(
                        spec_dict, runtime_type, optimization_level="balanced"
                    )

                    end_time = datetime.utcnow()
                    duration = (end_time - start_time).total_seconds()

                    runtime_results.append({
                        "iteration": i + 1,
                        "duration_seconds": duration,
                        "success": result.success,
                        "memory_estimate_mb": result.performance_metrics.get("memory_estimate_mb", 0),
                        "component_count": len(self._get_components_list(spec_dict))
                    })

                except Exception as e:
                    runtime_results.append({
                        "iteration": i + 1,
                        "duration_seconds": float('inf'),
                        "success": False,
                        "error": str(e)
                    })

            # Calculate statistics
            successful_results = [r for r in runtime_results if r["success"]]
            if successful_results:
                durations = [r["duration_seconds"] for r in successful_results]
                benchmark_results[runtime_type.value] = {
                    "avg_duration_seconds": sum(durations) / len(durations),
                    "min_duration_seconds": min(durations),
                    "max_duration_seconds": max(durations),
                    "success_rate": len(successful_results) / iterations,
                    "iterations": iterations,
                    "results": runtime_results
                }
            else:
                benchmark_results[runtime_type.value] = {
                    "avg_duration_seconds": float('inf'),
                    "success_rate": 0.0,
                    "iterations": iterations,
                    "results": runtime_results,
                    "error": "All iterations failed"
                }

        return {
            "benchmark_results": benchmark_results,
            "fastest_runtime": min(
                benchmark_results.keys(),
                key=lambda k: benchmark_results[k]["avg_duration_seconds"]
            ),
            "most_reliable_runtime": max(
                benchmark_results.keys(),
                key=lambda k: benchmark_results[k]["success_rate"]
            ),
            "specification_metadata": {
                "component_count": len(self._get_components_list(spec_dict)),
                "complexity_estimate": self._estimate_complexity(spec_dict)
            }
        }

    async def detect_performance_bottlenecks(self,
                                           spec_dict: Dict[str, Any],
                                           target_runtime: RuntimeType) -> Dict[str, Any]:
        """
        Detect performance bottlenecks in specification.

        Args:
            spec_dict: Genesis specification dictionary
            target_runtime: Target runtime type

        Returns:
            Bottleneck analysis with recommendations
        """
        bottlenecks = []
        recommendations = []

        try:
            converter = converter_factory.registry.get_converter(target_runtime)
            components = self._get_components_list(spec_dict)

            # Check component count
            if len(components) > 20:
                bottlenecks.append({
                    "type": "high_component_count",
                    "severity": "medium",
                    "description": f"High component count: {len(components)} components",
                    "impact": "May slow down conversion and execution"
                })
                recommendations.append("Consider breaking into smaller workflows")

            # Check component complexity
            complex_components = [
                c for c in components
                if c.get("type", "").startswith("genesis:crewai") or
                   len(c.get("provides", [])) > 3
            ]

            if complex_components:
                bottlenecks.append({
                    "type": "complex_components",
                    "severity": "medium",
                    "description": f"Complex components detected: {len(complex_components)}",
                    "components": [c.get("id") for c in complex_components],
                    "impact": "May require additional processing time"
                })
                recommendations.append("Optimize complex component configurations")

            # Check edge density
            total_edges = sum(len(c.get("provides", [])) for c in components)
            edge_density = total_edges / len(components) if components else 0

            if edge_density > 2.0:
                bottlenecks.append({
                    "type": "high_edge_density",
                    "severity": "low",
                    "description": f"High edge density: {edge_density:.2f} edges per component",
                    "impact": "May impact visualization and processing"
                })
                recommendations.append("Consider simplifying component connections")

            # Runtime-specific bottlenecks
            runtime_bottlenecks = await self._detect_runtime_specific_bottlenecks(
                spec_dict, converter
            )
            bottlenecks.extend(runtime_bottlenecks)

            return {
                "bottlenecks_detected": bottlenecks,
                "recommendations": recommendations,
                "severity_summary": {
                    "high": len([b for b in bottlenecks if b.get("severity") == "high"]),
                    "medium": len([b for b in bottlenecks if b.get("severity") == "medium"]),
                    "low": len([b for b in bottlenecks if b.get("severity") == "low"])
                },
                "analysis_metadata": {
                    "component_count": len(components),
                    "edge_count": total_edges,
                    "edge_density": edge_density,
                    "runtime_type": target_runtime.value
                }
            }

        except Exception as e:
            logger.error(f"Bottleneck detection failed: {e}")
            return {
                "bottlenecks_detected": [],
                "recommendations": [f"Bottleneck analysis failed: {e}"],
                "error": str(e)
            }

    def get_optimization_recommendations(self,
                                       performance_metrics: PerformanceMetrics) -> List[str]:
        """
        Get optimization recommendations based on performance metrics.

        Args:
            performance_metrics: Performance metrics from previous operations

        Returns:
            List of optimization recommendations
        """
        recommendations = []

        # Conversion duration recommendations
        if performance_metrics.conversion_duration_seconds > 10:
            recommendations.append(
                "Consider reducing component count or complexity for faster conversion"
            )

        # Memory usage recommendations
        if performance_metrics.memory_estimate_mb > 1000:
            recommendations.append(
                "High memory usage detected - consider optimizing large data components"
            )

        # Component complexity recommendations
        if performance_metrics.complexity_score > 5.0:
            recommendations.append(
                "High workflow complexity - consider breaking into smaller workflows"
            )

        # Edge count recommendations
        if performance_metrics.edge_count > 50:
            recommendations.append(
                "High edge count may impact performance - consider simplifying connections"
            )

        # General optimization recommendations
        if performance_metrics.optimization_level == "fast":
            recommendations.append(
                "Using fast optimization - consider 'balanced' or 'thorough' for better results"
            )

        return recommendations

    # Private helper methods

    async def _analyze_specification_performance(self,
                                               spec_dict: Dict[str, Any],
                                               converter) -> Dict[str, Any]:
        """Analyze specification for performance characteristics."""
        components = self._get_components_list(spec_dict)

        return {
            "component_count": len(components),
            "complexity_score": self._estimate_complexity(spec_dict),
            "estimated_memory_mb": self._estimate_memory_usage(spec_dict),
            "bottleneck_indicators": await self._identify_bottleneck_indicators(spec_dict, converter)
        }

    async def _apply_optimization_rules(self,
                                      spec_dict: Dict[str, Any],
                                      converter,
                                      optimization_level: OptimizationLevel,
                                      custom_rules: Optional[List[OptimizationRule]]) -> Tuple[Dict[str, Any], List[str]]:
        """Apply optimization rules to specification."""
        optimized_spec = spec_dict.copy()
        applied_optimizations = []

        # Get applicable rules
        rules = self.optimization_rules.copy()
        if custom_rules:
            rules.extend(custom_rules)

        # Filter rules by runtime type
        runtime_rules = [
            rule for rule in rules
            if not rule.runtime_types or converter.runtime_type in rule.runtime_types
        ]

        # Sort by priority
        runtime_rules.sort(key=lambda r: r.priority, reverse=True)

        # Apply rules based on optimization level
        for rule in runtime_rules:
            try:
                if rule.condition(optimized_spec, optimization_level):
                    optimized_spec = rule.optimization(optimized_spec)
                    applied_optimizations.append(rule.name)

                    # Limit optimizations for fast mode
                    if optimization_level == OptimizationLevel.FAST and len(applied_optimizations) >= 3:
                        break

            except Exception as e:
                logger.warning(f"Optimization rule {rule.name} failed: {e}")

        return optimized_spec, applied_optimizations

    async def _validate_optimizations(self,
                                    optimized_spec: Dict[str, Any],
                                    converter) -> Dict[str, Any]:
        """Validate that optimizations didn't break the specification."""
        try:
            validation_options = ValidationOptions(
                enable_type_checking=True,
                enable_edge_validation=True,
                strict_mode=False
            )

            validation_result = await converter.pre_conversion_validation(
                optimized_spec, validation_options
            )

            return {
                "valid": validation_result["valid"],
                "errors": validation_result.get("errors", []),
                "warnings": validation_result.get("warnings", [])
            }

        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Validation failed: {e}"],
                "warnings": []
            }

    def _calculate_performance_metrics(self,
                                     original_spec: Dict[str, Any],
                                     optimized_spec: Dict[str, Any],
                                     optimization_duration: float,
                                     applied_optimizations: List[str]) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics."""
        original_components = self._get_components_list(original_spec)
        optimized_components = self._get_components_list(optimized_spec)

        return PerformanceMetrics(
            conversion_duration_seconds=optimization_duration,
            validation_duration_seconds=0.0,  # Would be measured during actual validation
            component_count=len(optimized_components),
            edge_count=sum(len(c.get("provides", [])) for c in optimized_components),
            memory_estimate_mb=self._estimate_memory_usage(optimized_spec),
            complexity_score=self._estimate_complexity(optimized_spec),
            optimization_level="balanced",  # Default
            optimizations_applied=applied_optimizations,
            bottlenecks_detected=[],  # Would be populated by bottleneck detection
            recommendations=[]  # Would be populated by recommendation engine
        )

    def _record_performance_history(self,
                                  metrics: PerformanceMetrics,
                                  runtime_type: RuntimeType):
        """Record performance metrics for historical analysis."""
        self.performance_history.append({
            "timestamp": datetime.utcnow(),
            "runtime_type": runtime_type.value,
            "metrics": metrics
        })

        # Keep only last 100 entries
        if len(self.performance_history) > 100:
            self.performance_history = self.performance_history[-100:]

    def _initialize_optimization_rules(self) -> List[OptimizationRule]:
        """Initialize default optimization rules."""
        return [
            OptimizationRule(
                name="reduce_timeout_values",
                description="Reduce excessive timeout values for faster execution",
                condition=lambda spec, level: level in [OptimizationLevel.FAST, OptimizationLevel.BALANCED],
                optimization=self._optimize_timeouts,
                priority=8,
                runtime_types=[RuntimeType.LANGFLOW, RuntimeType.TEMPORAL]
            ),
            OptimizationRule(
                name="optimize_agent_temperature",
                description="Optimize agent temperature for consistency",
                condition=lambda spec, level: level != OptimizationLevel.FAST,
                optimization=self._optimize_agent_temperature,
                priority=6,
                runtime_types=[RuntimeType.LANGFLOW]
            ),
            OptimizationRule(
                name="enable_caching",
                description="Enable caching for compatible components",
                condition=lambda spec, level: level == OptimizationLevel.THOROUGH,
                optimization=self._enable_caching,
                priority=7,
                runtime_types=[RuntimeType.LANGFLOW]
            ),
            OptimizationRule(
                name="optimize_memory_usage",
                description="Optimize components for memory efficiency",
                condition=lambda spec, level: level in [OptimizationLevel.BALANCED, OptimizationLevel.THOROUGH],
                optimization=self._optimize_memory_usage,
                priority=5,
                runtime_types=[RuntimeType.LANGFLOW, RuntimeType.TEMPORAL]
            )
        ]

    def _optimize_timeouts(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize timeout values in components."""
        optimized_spec = spec_dict.copy()
        components = self._get_components_list(optimized_spec)

        for component in components:
            config = component.get("config", {})
            if "timeout" in config and isinstance(config["timeout"], (int, float)):
                if config["timeout"] > 60:
                    config["timeout"] = 60  # Max 60 seconds
                component["config"] = config

        return optimized_spec

    def _optimize_agent_temperature(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize agent temperature for consistency."""
        optimized_spec = spec_dict.copy()
        components = self._get_components_list(optimized_spec)

        for component in components:
            if "agent" in component.get("type", "").lower():
                config = component.get("config", {})
                if "temperature" in config and config["temperature"] > 0.7:
                    config["temperature"] = 0.7
                component["config"] = config

        return optimized_spec

    def _enable_caching(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Enable caching for compatible components."""
        optimized_spec = spec_dict.copy()
        components = self._get_components_list(optimized_spec)

        cacheable_types = ["genesis:knowledge_hub_search", "genesis:api_request", "genesis:mcp_tool"]

        for component in components:
            if component.get("type") in cacheable_types:
                config = component.get("config", {})
                if "cache_enabled" not in config:
                    config["cache_enabled"] = True
                component["config"] = config

        return optimized_spec

    def _optimize_memory_usage(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize components for memory efficiency."""
        optimized_spec = spec_dict.copy()
        components = self._get_components_list(optimized_spec)

        for component in components:
            config = component.get("config", {})

            # Limit max_tokens for memory efficiency
            if "max_tokens" in config and config["max_tokens"] > 2000:
                config["max_tokens"] = 2000

            # Optimize memory-intensive settings
            if "batch_size" in config and config["batch_size"] > 10:
                config["batch_size"] = 10

            component["config"] = config

        return optimized_spec

    async def _identify_bottleneck_indicators(self,
                                            spec_dict: Dict[str, Any],
                                            converter) -> List[str]:
        """Identify potential bottleneck indicators."""
        indicators = []
        components = self._get_components_list(spec_dict)

        # High component count
        if len(components) > 15:
            indicators.append("high_component_count")

        # Complex interconnections
        total_edges = sum(len(c.get("provides", [])) for c in components)
        if total_edges > 30:
            indicators.append("complex_interconnections")

        # Heavy components
        heavy_types = ["genesis:crewai_sequential_crew", "genesis:crewai_hierarchical_crew"]
        if any(c.get("type") in heavy_types for c in components):
            indicators.append("heavy_components")

        return indicators

    async def _detect_runtime_specific_bottlenecks(self,
                                                 spec_dict: Dict[str, Any],
                                                 converter) -> List[Dict[str, Any]]:
        """Detect runtime-specific performance bottlenecks."""
        bottlenecks = []

        if converter.runtime_type == RuntimeType.LANGFLOW:
            # Langflow-specific bottlenecks
            components = self._get_components_list(spec_dict)

            # Check for UI performance impact
            if len(components) > 25:
                bottlenecks.append({
                    "type": "langflow_ui_performance",
                    "severity": "medium",
                    "description": "High component count may impact Langflow UI performance",
                    "impact": "Slower flow visualization and editing"
                })

        elif converter.runtime_type == RuntimeType.TEMPORAL:
            # Temporal-specific bottlenecks
            pass  # Would implement Temporal-specific checks

        return bottlenecks

    def _get_components_list(self, spec_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract components list from specification."""
        components = spec_dict.get("components", [])

        if isinstance(components, dict):
            return [
                {**comp_data, "id": comp_id}
                for comp_id, comp_data in components.items()
            ]
        elif isinstance(components, list):
            return components
        else:
            return []

    def _estimate_complexity(self, spec_dict: Dict[str, Any]) -> float:
        """Estimate specification complexity score."""
        components = self._get_components_list(spec_dict)
        complexity = 0.0

        # Base complexity
        complexity += len(components) * 0.1

        # Component type complexity
        for component in components:
            comp_type = component.get("type", "")
            if "crewai" in comp_type:
                complexity += 0.5
            elif "agent" in comp_type:
                complexity += 0.3
            else:
                complexity += 0.1

            # Connection complexity
            provides = component.get("provides", [])
            complexity += len(provides) * 0.1

        return min(complexity, 10.0)  # Cap at 10.0

    def _estimate_memory_usage(self, spec_dict: Dict[str, Any]) -> int:
        """Estimate memory usage in MB."""
        components = self._get_components_list(spec_dict)
        base_memory = 100  # Base overhead

        for component in components:
            comp_type = component.get("type", "")
            if "agent" in comp_type.lower():
                base_memory += 200
            elif "crewai" in comp_type.lower():
                base_memory += 300
            else:
                base_memory += 50

        return base_memory


# Global optimizer instance
performance_optimizer = PerformanceOptimizer()