"""
Converter Factory for managing multiple runtime adapters.

This module implements the factory pattern for creating and managing
runtime-specific converters, providing a unified interface for
multi-runtime conversion support in Phase 3.
"""

from typing import Dict, Any, List, Optional, Set, Type
import asyncio
import logging
from datetime import datetime

from .base_converter import RuntimeConverter, RuntimeType, ConversionMode, ConversionResult, ValidationOptions

logger = logging.getLogger(__name__)


class ConverterRegistry:
    """Registry for managing runtime converter implementations."""

    def __init__(self):
        self._converters: Dict[RuntimeType, Type[RuntimeConverter]] = {}
        self._instances: Dict[RuntimeType, RuntimeConverter] = {}
        self._capabilities: Dict[RuntimeType, Dict[str, Any]] = {}

    def register_converter(self,
                          runtime_type: RuntimeType,
                          converter_class: Type[RuntimeConverter],
                          capabilities: Optional[Dict[str, Any]] = None):
        """
        Register a runtime converter.

        Args:
            runtime_type: The runtime type this converter supports
            converter_class: The converter class
            capabilities: Optional runtime capabilities metadata
        """
        self._converters[runtime_type] = converter_class
        self._capabilities[runtime_type] = capabilities or {}
        logger.info(f"Registered converter for runtime: {runtime_type.value}")

    def get_converter(self, runtime_type: RuntimeType) -> RuntimeConverter:
        """
        Get converter instance for runtime type.

        Args:
            runtime_type: The runtime type

        Returns:
            Converter instance

        Raises:
            ValueError: If runtime type is not supported
        """
        if runtime_type not in self._converters:
            available = list(self._converters.keys())
            raise ValueError(f"Unsupported runtime type: {runtime_type.value}. Available: {[r.value for r in available]}")

        # Return cached instance or create new one
        if runtime_type not in self._instances:
            converter_class = self._converters[runtime_type]
            self._instances[runtime_type] = converter_class(runtime_type)

        return self._instances[runtime_type]

    def get_available_runtimes(self) -> List[RuntimeType]:
        """Get list of available runtime types."""
        return list(self._converters.keys())

    def get_runtime_capabilities(self, runtime_type: RuntimeType) -> Dict[str, Any]:
        """Get capabilities for a specific runtime."""
        return self._capabilities.get(runtime_type, {})

    def clear_cache(self):
        """Clear cached converter instances."""
        self._instances.clear()


# Global registry instance
converter_registry = ConverterRegistry()


class ConverterFactory:
    """
    Factory for creating and managing runtime converters.

    Provides a unified interface for multi-runtime conversion with
    enhanced validation, performance optimization, and error handling.
    """

    def __init__(self, registry: Optional[ConverterRegistry] = None):
        """
        Initialize the converter factory.

        Args:
            registry: Optional converter registry (uses global if None)
        """
        self.registry = registry or converter_registry
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def convert_specification(self,
                                  spec_dict: Dict[str, Any],
                                  target_runtime: RuntimeType,
                                  variables: Optional[Dict[str, Any]] = None,
                                  validation_options: Optional[ValidationOptions] = None,
                                  optimization_level: str = "balanced") -> ConversionResult:
        """
        Convert Genesis specification to target runtime format.

        Args:
            spec_dict: Genesis specification dictionary
            target_runtime: Target runtime type
            variables: Runtime variables for resolution
            validation_options: Validation configuration options
            optimization_level: Performance optimization level

        Returns:
            ConversionResult with flow data and metadata

        Raises:
            ValueError: If runtime is not supported
            ConversionError: If conversion fails
        """
        conversion_start = datetime.utcnow()

        try:
            # Get converter for target runtime
            converter = self.registry.get_converter(target_runtime)

            # Pre-conversion validation if enabled
            validation_result = None
            if validation_options is None or validation_options.enable_type_checking:
                validation_result = await converter.pre_conversion_validation(
                    spec_dict, validation_options
                )

                if not validation_result["valid"]:
                    return ConversionResult(
                        success=False,
                        runtime_type=target_runtime,
                        errors=validation_result["errors"],
                        warnings=validation_result["warnings"],
                        metadata={
                            "validation_failed": True,
                            "validation_result": validation_result
                        }
                    )

            # Apply performance optimizations
            optimized_spec = spec_dict
            optimization_metadata = {}
            if optimization_level != "none":
                optimization_result = await converter.optimize_for_performance(
                    spec_dict, optimization_level
                )
                optimized_spec = optimization_result["spec"]
                optimization_metadata = optimization_result["optimization_metadata"]

            # Perform conversion
            result = await converter.convert_to_runtime(
                optimized_spec, variables, validation_options
            )

            # Add factory metadata
            conversion_duration = (datetime.utcnow() - conversion_start).total_seconds()
            result.metadata.update({
                "factory_metadata": {
                    "conversion_duration_seconds": conversion_duration,
                    "optimization_level": optimization_level,
                    "optimization_metadata": optimization_metadata,
                    "validation_performed": validation_result is not None,
                    "runtime_type": target_runtime.value
                }
            })

            if validation_result:
                result.metadata["validation_result"] = validation_result

            return result

        except Exception as e:
            self.logger.error(f"Conversion failed for runtime {target_runtime.value}: {e}")
            return ConversionResult(
                success=False,
                runtime_type=target_runtime,
                errors=[f"Conversion failed: {e}"],
                metadata={
                    "factory_metadata": {
                        "conversion_duration_seconds": (datetime.utcnow() - conversion_start).total_seconds(),
                        "error": str(e)
                    }
                }
            )

    async def validate_specification(self,
                                   spec_dict: Dict[str, Any],
                                   target_runtime: RuntimeType,
                                   validation_options: Optional[ValidationOptions] = None) -> Dict[str, Any]:
        """
        Validate Genesis specification for target runtime.

        Args:
            spec_dict: Genesis specification dictionary
            target_runtime: Target runtime type
            validation_options: Validation configuration options

        Returns:
            Validation result dictionary

        Raises:
            ValueError: If runtime is not supported
        """
        try:
            converter = self.registry.get_converter(target_runtime)
            return await converter.pre_conversion_validation(spec_dict, validation_options)

        except Exception as e:
            self.logger.error(f"Validation failed for runtime {target_runtime.value}: {e}")
            return {
                "valid": False,
                "errors": [f"Validation failed: {e}"],
                "warnings": [],
                "suggestions": [],
                "performance_hints": [],
                "validation_metadata": {
                    "runtime_type": target_runtime.value,
                    "error": str(e)
                }
            }

    async def get_supported_components(self, runtime_type: RuntimeType) -> Set[str]:
        """
        Get supported component types for a runtime.

        Args:
            runtime_type: Runtime type to query

        Returns:
            Set of supported Genesis component types

        Raises:
            ValueError: If runtime is not supported
        """
        converter = self.registry.get_converter(runtime_type)
        return converter.get_supported_components()

    async def check_runtime_compatibility(self,
                                        spec_dict: Dict[str, Any],
                                        runtime_types: Optional[List[RuntimeType]] = None) -> Dict[RuntimeType, Dict[str, Any]]:
        """
        Check specification compatibility across multiple runtimes.

        Args:
            spec_dict: Genesis specification dictionary
            runtime_types: List of runtime types to check (all if None)

        Returns:
            Dictionary mapping runtime types to compatibility results
        """
        if runtime_types is None:
            runtime_types = self.registry.get_available_runtimes()

        compatibility_results = {}

        for runtime_type in runtime_types:
            try:
                converter = self.registry.get_converter(runtime_type)
                validation_result = await converter.pre_conversion_validation(spec_dict)

                compatibility_results[runtime_type] = {
                    "compatible": validation_result["valid"],
                    "errors": validation_result["errors"],
                    "warnings": validation_result["warnings"],
                    "suggestions": validation_result["suggestions"],
                    "performance_hints": validation_result.get("performance_hints", []),
                    "metadata": validation_result.get("validation_metadata", {})
                }

            except Exception as e:
                self.logger.error(f"Compatibility check failed for {runtime_type.value}: {e}")
                compatibility_results[runtime_type] = {
                    "compatible": False,
                    "errors": [f"Compatibility check failed: {e}"],
                    "warnings": [],
                    "suggestions": [],
                    "performance_hints": [],
                    "metadata": {"error": str(e)}
                }

        return compatibility_results

    async def convert_to_multiple_runtimes(self,
                                         spec_dict: Dict[str, Any],
                                         runtime_types: List[RuntimeType],
                                         variables: Optional[Dict[str, Any]] = None,
                                         validation_options: Optional[ValidationOptions] = None,
                                         optimization_level: str = "balanced") -> Dict[RuntimeType, ConversionResult]:
        """
        Convert specification to multiple runtime formats concurrently.

        Args:
            spec_dict: Genesis specification dictionary
            runtime_types: List of target runtime types
            variables: Runtime variables for resolution
            validation_options: Validation configuration options
            optimization_level: Performance optimization level

        Returns:
            Dictionary mapping runtime types to conversion results
        """
        conversion_tasks = []

        for runtime_type in runtime_types:
            task = self.convert_specification(
                spec_dict, runtime_type, variables, validation_options, optimization_level
            )
            conversion_tasks.append((runtime_type, task))

        # Run conversions concurrently
        results = {}
        conversion_results = await asyncio.gather(
            *[task for _, task in conversion_tasks],
            return_exceptions=True
        )

        for (runtime_type, _), result in zip(conversion_tasks, conversion_results):
            if isinstance(result, Exception):
                self.logger.error(f"Conversion to {runtime_type.value} failed: {result}")
                results[runtime_type] = ConversionResult(
                    success=False,
                    runtime_type=runtime_type,
                    errors=[f"Conversion failed: {result}"]
                )
            else:
                results[runtime_type] = result

        return results

    def get_runtime_info(self, runtime_type: RuntimeType) -> Dict[str, Any]:
        """
        Get information about a specific runtime.

        Args:
            runtime_type: Runtime type to query

        Returns:
            Runtime information dictionary

        Raises:
            ValueError: If runtime is not supported
        """
        converter = self.registry.get_converter(runtime_type)
        info = converter.get_runtime_info()

        # Add registry capabilities
        registry_capabilities = self.registry.get_runtime_capabilities(runtime_type)
        if registry_capabilities:
            info["registry_capabilities"] = registry_capabilities

        return info

    def get_available_runtimes(self) -> List[Dict[str, Any]]:
        """
        Get information about all available runtimes.

        Returns:
            List of runtime information dictionaries
        """
        runtimes = []

        for runtime_type in self.registry.get_available_runtimes():
            try:
                info = self.get_runtime_info(runtime_type)
                runtimes.append(info)
            except Exception as e:
                self.logger.warning(f"Could not get info for runtime {runtime_type.value}: {e}")
                runtimes.append({
                    "name": runtime_type.value,
                    "available": False,
                    "error": str(e)
                })

        return runtimes

    async def optimize_specification(self,
                                   spec_dict: Dict[str, Any],
                                   target_runtime: RuntimeType,
                                   optimization_level: str = "balanced") -> Dict[str, Any]:
        """
        Optimize specification for a target runtime.

        Args:
            spec_dict: Genesis specification dictionary
            target_runtime: Target runtime type
            optimization_level: Performance optimization level

        Returns:
            Optimization result with optimized spec and metadata

        Raises:
            ValueError: If runtime is not supported
        """
        converter = self.registry.get_converter(target_runtime)
        return await converter.optimize_for_performance(spec_dict, optimization_level)


# Global factory instance
converter_factory = ConverterFactory()


def register_converter(runtime_type: RuntimeType,
                      converter_class: Type[RuntimeConverter],
                      capabilities: Optional[Dict[str, Any]] = None):
    """
    Convenience function to register a converter with the global registry.

    Args:
        runtime_type: The runtime type
        converter_class: The converter class
        capabilities: Optional runtime capabilities metadata
    """
    converter_registry.register_converter(runtime_type, converter_class, capabilities)


def get_converter_factory() -> ConverterFactory:
    """Get the global converter factory instance."""
    return converter_factory