"""
Abstract Base Converter Interface for Multi-Runtime Support.

This module provides the foundation for Phase 3: Conversion Architecture Enhancement,
implementing a pluggable converter system that supports multiple runtime targets
with enhanced validation, type compatibility checking, and performance optimization.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Protocol, runtime_checkable, Set, Tuple
from enum import Enum
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


class RuntimeType(Enum):
    """Supported runtime types for conversions."""
    LANGFLOW = "langflow"
    TEMPORAL = "temporal"
    KAFKA = "kafka"
    AIRFLOW = "airflow"
    PREFECT = "prefect"
    GENERIC = "generic"


class ConversionMode(Enum):
    """Conversion direction modes."""
    SPEC_TO_RUNTIME = "spec_to_runtime"
    RUNTIME_TO_SPEC = "runtime_to_spec"


class ConversionResult:
    """Result of a conversion operation with detailed metadata."""

    def __init__(self,
                 success: bool,
                 runtime_type: RuntimeType,
                 flow_data: Optional[Dict[str, Any]] = None,
                 errors: Optional[List[str]] = None,
                 warnings: Optional[List[str]] = None,
                 metadata: Optional[Dict[str, Any]] = None,
                 performance_metrics: Optional[Dict[str, Any]] = None):
        self.success = success
        self.runtime_type = runtime_type
        self.flow_data = flow_data or {}
        self.errors = errors or []
        self.warnings = warnings or []
        self.metadata = metadata or {}
        self.performance_metrics = performance_metrics or {}
        self.timestamp = datetime.utcnow()


@dataclass
class ComponentCompatibility:
    """Component compatibility information for runtime validation."""
    genesis_type: str
    runtime_component: str
    supported_inputs: List[str]
    supported_outputs: List[str]
    configuration_schema: Dict[str, Any]
    constraints: List[str]
    performance_hints: Dict[str, Any]


@dataclass
class EdgeValidationResult:
    """Result of edge validation with detailed diagnostics."""
    valid: bool
    source_component: str
    target_component: str
    connection_type: str
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]
    compatibility_score: float  # 0.0 to 1.0


@dataclass
class ValidationOptions:
    """Options for controlling validation behavior."""
    enable_type_checking: bool = True
    enable_performance_hints: bool = True
    enable_edge_validation: bool = True
    strict_mode: bool = False
    cache_results: bool = True


@runtime_checkable
class RuntimeCapability(Protocol):
    """Protocol for runtime capability metadata."""

    @property
    def supported_components(self) -> List[str]:
        """List of supported Genesis component types."""
        ...

    @property
    def bidirectional_support(self) -> bool:
        """Whether runtime supports bidirectional conversion."""
        ...

    @property
    def streaming_support(self) -> bool:
        """Whether runtime supports streaming operations."""
        ...


class RuntimeConverter(ABC):
    """
    Enhanced abstract base class for all runtime converters.

    This interface defines the contract that all runtime converters must implement
    to support the Genesis multi-runtime architecture with Phase 3 enhancements:
    - Enhanced validation with type compatibility checking
    - Comprehensive edge validation and connection rules
    - Performance optimization capabilities
    - Support for future runtime targets
    """

    def __init__(self, runtime_type: RuntimeType):
        """
        Initialize the runtime converter.

        Args:
            runtime_type: The type of runtime this converter supports
        """
        self.runtime_type = runtime_type
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.validation_enabled = True
        self.performance_mode = "balanced"  # "fast", "balanced", "thorough"
        self._component_cache = {}
        self._validation_cache = {}

    @abstractmethod
    def get_runtime_info(self) -> Dict[str, Any]:
        """
        Return runtime capabilities and metadata.

        Returns:
            Dictionary containing:
            - name: Runtime name
            - version: Runtime version
            - capabilities: List of supported features
            - supported_components: List of Genesis component types
            - bidirectional_support: Boolean indicating reverse conversion support
            - streaming_support: Boolean indicating streaming support
            - metadata: Additional runtime-specific information
        """
        pass

    @abstractmethod
    def validate_specification(self, spec: Dict[str, Any]) -> List[str]:
        """
        Validate Genesis specification for this runtime.

        Args:
            spec: Genesis specification dictionary

        Returns:
            List of validation error messages (empty if valid)
        """
        pass

    @abstractmethod
    async def convert_to_runtime(self,
                               spec: Dict[str, Any],
                               variables: Optional[Dict[str, Any]] = None,
                               validation_options: Optional[ValidationOptions] = None) -> ConversionResult:
        """
        Convert Genesis specification to runtime-specific format with enhanced validation.

        Args:
            spec: Genesis specification dictionary
            variables: Runtime variables for resolution
            validation_options: Validation configuration options

        Returns:
            ConversionResult with flow data and metadata

        Raises:
            ConversionError: If conversion fails
            NotImplementedError: If runtime doesn't support this direction
        """
        pass

    @abstractmethod
    async def convert_from_runtime(self, runtime_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert runtime format back to Genesis specification.

        Args:
            runtime_spec: Runtime-specific configuration

        Returns:
            Genesis specification dictionary

        Raises:
            ConversionError: If conversion fails
            NotImplementedError: If runtime doesn't support bidirectional conversion
        """
        pass

    @abstractmethod
    def supports_component_type(self, component_type: str) -> bool:
        """
        Check if runtime supports given Genesis component type.

        Args:
            component_type: Genesis component type (e.g., "genesis:agent")

        Returns:
            True if component type is supported
        """
        pass

    @abstractmethod
    def validate_component_compatibility(self,
                                       component: Dict[str, Any]) -> ComponentCompatibility:
        """
        Validate if component is compatible with this runtime.

        Args:
            component: Component specification

        Returns:
            ComponentCompatibility with detailed compatibility information
        """
        pass

    @abstractmethod
    def get_runtime_constraints(self) -> Dict[str, Any]:
        """Get runtime-specific constraints and limitations."""
        pass

    @abstractmethod
    async def validate_edge_connection(self,
                                     source_comp: Dict[str, Any],
                                     target_comp: Dict[str, Any],
                                     connection: Dict[str, Any]) -> EdgeValidationResult:
        """
        Enhanced edge validation with runtime-specific rules.

        Args:
            source_comp: Source component specification
            target_comp: Target component specification
            connection: Connection/provides specification

        Returns:
            EdgeValidationResult with detailed validation information
        """
        pass

    def get_supported_conversion_modes(self) -> List[ConversionMode]:
        """
        Get list of supported conversion modes.

        Returns:
            List of supported conversion modes
        """
        modes = [ConversionMode.SPEC_TO_RUNTIME]

        # Check if bidirectional conversion is supported
        try:
            info = self.get_runtime_info()
            if info.get("bidirectional_support", False):
                modes.append(ConversionMode.RUNTIME_TO_SPEC)
        except Exception as e:
            self.logger.warning(f"Could not determine bidirectional support: {e}")

        return modes

    def validate_conversion_mode(self, mode: ConversionMode) -> bool:
        """
        Validate if converter supports the given conversion mode.

        Args:
            mode: Conversion mode to validate

        Returns:
            True if mode is supported
        """
        return mode in self.get_supported_conversion_modes()

    async def convert(self,
                    data: Dict[str, Any],
                    mode: ConversionMode,
                    variables: Optional[Dict[str, Any]] = None,
                    validation_options: Optional[ValidationOptions] = None) -> ConversionResult:
        """
        Generic conversion method that dispatches to appropriate converter.

        Args:
            data: Data to convert
            mode: Conversion direction
            variables: Runtime variables for resolution
            validation_options: Validation configuration options

        Returns:
            ConversionResult with converted data and metadata

        Raises:
            ConversionError: If conversion fails
            ValueError: If mode is not supported
        """
        if not self.validate_conversion_mode(mode):
            raise ValueError(f"Conversion mode {mode.value} not supported by {self.runtime_type.value}")

        if mode == ConversionMode.SPEC_TO_RUNTIME:
            return await self.convert_to_runtime(data, variables, validation_options)
        elif mode == ConversionMode.RUNTIME_TO_SPEC:
            result = await self.convert_from_runtime(data)
            return ConversionResult(
                success=True,
                runtime_type=self.runtime_type,
                flow_data=result
            )
        else:
            raise ValueError(f"Unknown conversion mode: {mode.value}")

    async def pre_conversion_validation(self,
                                      spec_dict: Dict[str, Any],
                                      validation_options: Optional[ValidationOptions] = None) -> Dict[str, Any]:
        """
        Comprehensive pre-conversion validation with runtime-specific checks.

        Args:
            spec_dict: Genesis specification dictionary
            validation_options: Validation configuration options

        Returns:
            Validation result with errors, warnings, and performance hints
        """
        validation_start = datetime.utcnow()
        options = validation_options or ValidationOptions()

        errors = []
        warnings = []
        suggestions = []
        performance_hints = []

        try:
            # Component compatibility validation
            components = self._get_components_list(spec_dict)

            if options.enable_type_checking:
                # Check each component compatibility
                for component in components:
                    try:
                        compatibility = self.validate_component_compatibility(component)

                        if compatibility.constraints:
                            warnings.extend([
                                f"Component {component.get('id')}: {constraint}"
                                for constraint in compatibility.constraints
                            ])

                        if options.enable_performance_hints and compatibility.performance_hints:
                            performance_hints.append({
                                "component": component.get("id"),
                                "hints": compatibility.performance_hints
                            })

                    except Exception as e:
                        errors.append(f"Component {component.get('id')} compatibility check failed: {e}")

            # Edge validation
            if options.enable_edge_validation:
                edge_results = await self._validate_all_edges(components)

                for edge_result in edge_results:
                    if not edge_result.valid:
                        errors.extend([
                            f"Edge {edge_result.source_component} -> {edge_result.target_component}: {error}"
                            for error in edge_result.errors
                        ])

                    warnings.extend([
                        f"Edge {edge_result.source_component} -> {edge_result.target_component}: {warning}"
                        for warning in edge_result.warnings
                    ])

                    suggestions.extend(edge_result.suggestions)

            # Runtime constraints validation
            constraints = self.get_runtime_constraints()
            constraint_violations = self._check_runtime_constraints(spec_dict, constraints)
            errors.extend(constraint_violations)

            validation_duration = (datetime.utcnow() - validation_start).total_seconds()

            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "suggestions": suggestions,
                "performance_hints": performance_hints,
                "validation_metadata": {
                    "runtime_type": self.runtime_type.value,
                    "validation_duration_seconds": validation_duration,
                    "component_count": len(components),
                    "edge_count": len([r for r in (await self._validate_all_edges(components))]) if options.enable_edge_validation else 0,
                    "constraints_checked": len(constraints)
                }
            }

        except Exception as e:
            self.logger.error(f"Pre-conversion validation failed: {e}")
            return {
                "valid": False,
                "errors": [f"Validation failed: {e}"],
                "warnings": [],
                "suggestions": [],
                "performance_hints": [],
                "validation_metadata": {
                    "runtime_type": self.runtime_type.value,
                    "validation_duration_seconds": (datetime.utcnow() - validation_start).total_seconds(),
                    "error": str(e)
                }
            }

    async def optimize_for_performance(self,
                                     spec_dict: Dict[str, Any],
                                     optimization_level: str = "balanced") -> Dict[str, Any]:
        """
        Apply performance optimizations to specification.

        Args:
            spec_dict: Genesis specification
            optimization_level: "fast", "balanced", "thorough"

        Returns:
            Optimized specification with performance metadata
        """
        optimized_spec = spec_dict.copy()
        optimizations_applied = []

        try:
            # Component-level optimizations
            components = self._get_components_list(spec_dict)

            if optimization_level in ["balanced", "thorough"]:
                # Optimize component configurations
                for component in components:
                    original_config = component.get("config", {})
                    optimized_config = await self._optimize_component_config(
                        component, optimization_level
                    )

                    if optimized_config != original_config:
                        component["config"] = optimized_config
                        optimizations_applied.append(f"Optimized config for {component.get('id')}")

            if optimization_level == "thorough":
                # Advanced optimizations
                optimized_spec = await self._apply_advanced_optimizations(optimized_spec)
                optimizations_applied.append("Applied advanced workflow optimizations")

            # Edge optimizations
            edge_optimizations = await self._optimize_edges(components)
            optimizations_applied.extend(edge_optimizations)

            return {
                "spec": optimized_spec,
                "optimizations_applied": optimizations_applied,
                "optimization_metadata": {
                    "level": optimization_level,
                    "runtime_type": self.runtime_type.value,
                    "component_count": len(components),
                    "optimization_count": len(optimizations_applied)
                }
            }

        except Exception as e:
            self.logger.error(f"Performance optimization failed: {e}")
            return {
                "spec": spec_dict,  # Return original on error
                "optimizations_applied": [],
                "optimization_metadata": {
                    "level": optimization_level,
                    "runtime_type": self.runtime_type.value,
                    "error": str(e)
                }
            }

    def enable_validation(self, enabled: bool = True):
        """Enable or disable validation during conversion."""
        self.validation_enabled = enabled

    def set_performance_mode(self, mode: str):
        """Set performance mode: 'fast', 'balanced', or 'thorough'."""
        if mode in ["fast", "balanced", "thorough"]:
            self.performance_mode = mode
        else:
            raise ValueError(f"Invalid performance mode: {mode}")

    # Protected helper methods

    def _get_components_list(self, spec_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract components list from specification."""
        components = spec_dict.get("components", [])

        if isinstance(components, dict):
            # Convert dict format to list
            return [
                {**comp_data, "id": comp_id}
                for comp_id, comp_data in components.items()
            ]
        elif isinstance(components, list):
            return components
        else:
            return []

    async def _validate_all_edges(self, components: List[Dict[str, Any]]) -> List[EdgeValidationResult]:
        """Validate all edges in the component graph."""
        edge_results = []
        component_lookup = {comp.get("id"): comp for comp in components}

        for component in components:
            provides = component.get("provides", [])

            for connection in provides:
                if isinstance(connection, dict):
                    target_id = connection.get("in")
                    target_comp = component_lookup.get(target_id)

                    if target_comp:
                        edge_result = await self.validate_edge_connection(
                            component, target_comp, connection
                        )
                        edge_results.append(edge_result)

        return edge_results

    def _check_runtime_constraints(self,
                                 spec_dict: Dict[str, Any],
                                 constraints: Dict[str, Any]) -> List[str]:
        """Check specification against runtime constraints."""
        violations = []

        try:
            # Component count limits
            max_components = constraints.get("max_components")
            if max_components:
                components = self._get_components_list(spec_dict)
                if len(components) > max_components:
                    violations.append(
                        f"Too many components: {len(components)} > {max_components}"
                    )

            # Memory limits
            max_memory = constraints.get("max_memory_mb")
            if max_memory:
                estimated_memory = self._estimate_memory_usage(spec_dict)
                if estimated_memory > max_memory:
                    violations.append(
                        f"Estimated memory usage too high: {estimated_memory}MB > {max_memory}MB"
                    )

            # Concurrency limits
            max_concurrent = constraints.get("max_concurrent_tasks")
            if max_concurrent:
                concurrent_estimate = self._estimate_concurrency(spec_dict)
                if concurrent_estimate > max_concurrent:
                    violations.append(
                        f"Too many concurrent tasks: {concurrent_estimate} > {max_concurrent}"
                    )

        except Exception as e:
            self.logger.warning(f"Error checking runtime constraints: {e}")

        return violations

    def _estimate_memory_usage(self, spec_dict: Dict[str, Any]) -> int:
        """Estimate memory usage in MB."""
        # Basic estimation - subclasses can provide runtime-specific estimates
        components = self._get_components_list(spec_dict)
        base_memory = 100  # Base overhead

        for component in components:
            comp_type = component.get("type", "")
            if "agent" in comp_type.lower():
                base_memory += 200  # Agents use more memory
            elif "model" in comp_type.lower():
                base_memory += 500  # Models use significant memory
            else:
                base_memory += 50   # Other components

        return base_memory

    def _estimate_concurrency(self, spec_dict: Dict[str, Any]) -> int:
        """Estimate concurrent task count."""
        # Basic estimation - count parallel branches
        components = self._get_components_list(spec_dict)

        # Count components that can run in parallel
        parallel_components = 0
        for component in components:
            provides = component.get("provides", [])
            if len(provides) > 1:  # Component feeds multiple targets
                parallel_components += len(provides) - 1

        return max(1, parallel_components)

    async def _optimize_component_config(self,
                                       component: Dict[str, Any],
                                       optimization_level: str) -> Dict[str, Any]:
        """Optimize component configuration for performance."""
        config = component.get("config", {}).copy()

        # Default optimizations - subclasses can override
        if optimization_level == "fast":
            # Fast mode optimizations
            if "timeout" in config and config["timeout"] > 30:
                config["timeout"] = 30  # Reduce timeouts

        elif optimization_level == "balanced":
            # Balanced optimizations
            if "temperature" in config and config["temperature"] > 0.7:
                config["temperature"] = 0.7  # Optimize for consistency

        elif optimization_level == "thorough":
            # Thorough optimizations
            if "max_tokens" in config and config["max_tokens"] > 2000:
                config["max_tokens"] = 2000  # Limit token usage

        return config

    async def _apply_advanced_optimizations(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Apply advanced workflow optimizations."""
        # Default implementation - subclasses can provide runtime-specific optimizations
        optimized_spec = spec_dict.copy()

        # Add caching configurations
        components = self._get_components_list(optimized_spec)
        for component in components:
            if component.get("type") in ["genesis:knowledge_hub_search", "genesis:api_request"]:
                config = component.get("config", {})
                if "cache_enabled" not in config:
                    config["cache_enabled"] = True
                    component["config"] = config

        return optimized_spec

    async def _optimize_edges(self, components: List[Dict[str, Any]]) -> List[str]:
        """Optimize edge connections for performance."""
        optimizations = []

        # Detect and optimize common patterns
        for component in components:
            provides = component.get("provides", [])

            # Batch multiple connections to same target
            target_groups = {}
            for connection in provides:
                if isinstance(connection, dict):
                    target = connection.get("in")
                    if target:
                        if target not in target_groups:
                            target_groups[target] = []
                        target_groups[target].append(connection)

            # Suggest batching for multiple connections to same target
            for target, connections in target_groups.items():
                if len(connections) > 1:
                    optimizations.append(
                        f"Consider batching {len(connections)} connections to {target}"
                    )

        return optimizations


class ConversionError(Exception):
    """Exception raised when conversion fails."""

    def __init__(self, message: str, runtime_type: str, conversion_mode: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.runtime_type = runtime_type
        self.conversion_mode = conversion_mode
        self.details = details or {}


class ConverterValidationError(ConversionError):
    """Exception raised when specification validation fails."""

    def __init__(self, validation_errors: List[str], runtime_type: str):
        message = f"Specification validation failed for {runtime_type}: {'; '.join(validation_errors)}"
        super().__init__(message, runtime_type, "validation")
        self.validation_errors = validation_errors


class ComponentNotSupportedError(ConversionError):
    """Exception raised when a component type is not supported by the runtime."""

    def __init__(self, component_type: str, runtime_type: str):
        message = f"Component type '{component_type}' is not supported by runtime '{runtime_type}'"
        super().__init__(message, runtime_type, "component_support")
        self.component_type = component_type