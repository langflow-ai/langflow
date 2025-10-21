"""
Runtime Registry for managing available converters.

This module provides a centralized registry for discovering and managing
runtime converters in the Genesis multi-runtime architecture.
"""

from typing import Dict, List, Optional, Type, Any
from collections import defaultdict
import logging
from concurrent.futures import ThreadPoolExecutor
import asyncio

from .base_converter import RuntimeConverter, RuntimeType, ConversionMode, ConversionError

logger = logging.getLogger(__name__)


class RuntimeRegistry:
    """
    Centralized registry for managing runtime converters.

    The registry maintains a collection of available converters and provides
    methods for discovery, selection, and capability querying.
    """

    def __init__(self):
        """Initialize the runtime registry."""
        self._converters: Dict[RuntimeType, RuntimeConverter] = {}
        self._converter_classes: Dict[RuntimeType, Type[RuntimeConverter]] = {}
        self._capabilities_cache: Dict[RuntimeType, Dict[str, Any]] = {}
        self._component_support_cache: Dict[str, List[RuntimeType]] = defaultdict(list)

    def register_converter(self, converter: RuntimeConverter) -> None:
        """
        Register a runtime converter.

        Args:
            converter: RuntimeConverter instance to register

        Raises:
            ValueError: If converter is already registered for this runtime
        """
        runtime_type = converter.runtime_type

        if runtime_type in self._converters:
            existing_converter = self._converters[runtime_type]
            logger.warning(
                f"Overriding existing converter for {runtime_type.value}: "
                f"{existing_converter.__class__.__name__} -> {converter.__class__.__name__}"
            )

        self._converters[runtime_type] = converter
        self._converter_classes[runtime_type] = converter.__class__

        # Cache runtime capabilities
        try:
            self._capabilities_cache[runtime_type] = converter.get_runtime_info()
            logger.info(f"Registered converter for runtime: {runtime_type.value}")
        except Exception as e:
            logger.error(f"Failed to cache capabilities for {runtime_type.value}: {e}")

        # Update component support cache
        self._update_component_support_cache(converter)

    def register_converter_class(self, runtime_type: RuntimeType, converter_class: Type[RuntimeConverter]) -> None:
        """
        Register a converter class for lazy instantiation.

        Args:
            runtime_type: Runtime type for the converter
            converter_class: Converter class to register
        """
        self._converter_classes[runtime_type] = converter_class
        logger.info(f"Registered converter class for runtime: {runtime_type.value}")

    def get_converter(self, runtime: str) -> Optional[RuntimeConverter]:
        """
        Get converter for specified runtime.

        Args:
            runtime: Runtime name (e.g., "langflow", "temporal")

        Returns:
            RuntimeConverter instance or None if not found
        """
        try:
            runtime_type = RuntimeType(runtime.lower())
        except ValueError:
            logger.warning(f"Unknown runtime type: {runtime}")
            return None

        # Return existing instance
        if runtime_type in self._converters:
            return self._converters[runtime_type]

        # Try lazy instantiation
        if runtime_type in self._converter_classes:
            try:
                converter_class = self._converter_classes[runtime_type]
                converter = converter_class(runtime_type)
                self.register_converter(converter)
                return converter
            except Exception as e:
                logger.error(f"Failed to instantiate converter for {runtime}: {e}")
                return None

        logger.warning(f"No converter registered for runtime: {runtime}")
        return None

    def list_available_runtimes(self) -> List[str]:
        """
        List all registered runtime converters.

        Returns:
            List of runtime names
        """
        available_runtimes = []

        # Add instantiated converters
        available_runtimes.extend([rt.value for rt in self._converters.keys()])

        # Add registered classes
        for runtime_type in self._converter_classes.keys():
            if runtime_type.value not in available_runtimes:
                available_runtimes.append(runtime_type.value)

        return sorted(available_runtimes)

    def get_runtime_capabilities(self, runtime: str) -> Optional[Dict[str, Any]]:
        """
        Get capabilities for a specific runtime.

        Args:
            runtime: Runtime name

        Returns:
            Runtime capabilities dictionary or None if not found
        """
        try:
            runtime_type = RuntimeType(runtime.lower())
        except ValueError:
            return None

        # Return cached capabilities
        if runtime_type in self._capabilities_cache:
            return self._capabilities_cache[runtime_type].copy()

        # Try to get from converter
        converter = self.get_converter(runtime)
        if converter:
            try:
                capabilities = converter.get_runtime_info()
                self._capabilities_cache[runtime_type] = capabilities
                return capabilities.copy()
            except Exception as e:
                logger.error(f"Failed to get capabilities for {runtime}: {e}")

        return None

    def find_converters_for_component(self, component_type: str) -> List[str]:
        """
        Find all runtimes that support a specific component type.

        Args:
            component_type: Genesis component type (e.g., "genesis:agent")

        Returns:
            List of runtime names that support the component
        """
        # Check cache first
        if component_type in self._component_support_cache:
            return [rt.value for rt in self._component_support_cache[component_type]]

        supported_runtimes = []

        # Check all available converters
        for runtime_name in self.list_available_runtimes():
            converter = self.get_converter(runtime_name)
            if converter and converter.supports_component_type(component_type):
                supported_runtimes.append(runtime_name)

        return supported_runtimes

    def get_best_runtime_for_spec(self, spec: Dict[str, Any]) -> Optional[str]:
        """
        Get the best runtime for a given specification.

        Args:
            spec: Genesis specification dictionary

        Returns:
            Best runtime name or None if no suitable runtime found
        """
        if not spec.get("components"):
            return None

        # Extract component types from spec
        components = spec["components"]
        component_types = set()

        if isinstance(components, list):
            for comp in components:
                if isinstance(comp, dict) and "type" in comp:
                    component_types.add(comp["type"])
        elif isinstance(components, dict):
            for comp_data in components.values():
                if isinstance(comp_data, dict) and "type" in comp_data:
                    component_types.add(comp_data["type"])

        if not component_types:
            return None

        # Score runtimes based on component support
        runtime_scores = defaultdict(int)

        for component_type in component_types:
            supported_runtimes = self.find_converters_for_component(component_type)
            for runtime in supported_runtimes:
                runtime_scores[runtime] += 1

        if not runtime_scores:
            return None

        # Find runtime with highest support score
        best_runtime = max(runtime_scores.items(), key=lambda x: x[1])

        # Only return if runtime supports all components
        if best_runtime[1] == len(component_types):
            return best_runtime[0]

        logger.warning(
            f"No runtime supports all components. Best partial support: "
            f"{best_runtime[0]} ({best_runtime[1]}/{len(component_types)} components)"
        )
        return best_runtime[0]  # Return best partial match

    async def validate_spec_for_runtime(self, spec: Dict[str, Any], runtime: str) -> Dict[str, Any]:
        """
        Validate specification for a specific runtime.

        Args:
            spec: Genesis specification dictionary
            runtime: Runtime name

        Returns:
            Validation result with errors and warnings
        """
        converter = self.get_converter(runtime)
        if not converter:
            return {
                "valid": False,
                "errors": [f"Runtime '{runtime}' not found"],
                "warnings": [],
                "runtime": runtime
            }

        try:
            validation_errors = converter.validate_specification(spec)
            return {
                "valid": len(validation_errors) == 0,
                "errors": validation_errors,
                "warnings": [],
                "runtime": runtime
            }
        except Exception as e:
            logger.error(f"Validation failed for runtime {runtime}: {e}")
            return {
                "valid": False,
                "errors": [f"Validation failed: {str(e)}"],
                "warnings": [],
                "runtime": runtime
            }

    async def convert_with_runtime(self, data: Dict[str, Any], runtime: str,
                                  mode: ConversionMode) -> Dict[str, Any]:
        """
        Convert data using specified runtime converter.

        Args:
            data: Data to convert
            runtime: Runtime name
            mode: Conversion mode

        Returns:
            Converted data

        Raises:
            ConversionError: If conversion fails
        """
        converter = self.get_converter(runtime)
        if not converter:
            raise ConversionError(
                f"Runtime '{runtime}' not found",
                runtime,
                mode.value
            )

        return converter.convert(data, mode)

    def get_runtime_compatibility_matrix(self) -> Dict[str, Dict[str, Any]]:
        """
        Get compatibility matrix for all runtimes.

        Returns:
            Dictionary mapping runtime names to their compatibility info
        """
        matrix = {}

        for runtime_name in self.list_available_runtimes():
            capabilities = self.get_runtime_capabilities(runtime_name)
            if capabilities:
                matrix[runtime_name] = {
                    "supported_components": capabilities.get("supported_components", []),
                    "bidirectional_support": capabilities.get("bidirectional_support", False),
                    "streaming_support": capabilities.get("streaming_support", False),
                    "conversion_modes": [mode.value for mode in self._get_conversion_modes(runtime_name)]
                }

        return matrix

    def _update_component_support_cache(self, converter: RuntimeConverter) -> None:
        """Update component support cache for a converter."""
        try:
            capabilities = converter.get_runtime_info()
            supported_components = capabilities.get("supported_components", [])

            for component_type in supported_components:
                if converter.runtime_type not in self._component_support_cache[component_type]:
                    self._component_support_cache[component_type].append(converter.runtime_type)

        except Exception as e:
            logger.warning(f"Failed to update component support cache: {e}")

    def _get_conversion_modes(self, runtime: str) -> List[ConversionMode]:
        """Get supported conversion modes for a runtime."""
        converter = self.get_converter(runtime)
        if converter:
            return converter.get_supported_conversion_modes()
        return []

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._capabilities_cache.clear()
        self._component_support_cache.clear()
        logger.info("Runtime registry cache cleared")


# Global registry instance
runtime_registry = RuntimeRegistry()