"""
Runtime Services Module for Phase 3: Conversion Architecture Enhancement.

This module provides the foundation for converting Genesis specifications to different
runtime targets with enhanced validation, type compatibility checking, and performance
optimization.

The module includes:
- Base converter interface (base_converter.py)
- Converter factory for managing multiple runtimes (converter_factory.py)
- Langflow-specific converter implementation (langflow_converter.py)
- Future runtime adapters (temporal, kafka, etc.)

Usage:
    from langflow.services.runtime import converter_factory, LangflowConverter
    from langflow.services.runtime.base_converter import RuntimeType, ValidationOptions

    # Get a converter for Langflow
    converter = converter_factory.registry.get_converter(RuntimeType.LANGFLOW)

    # Convert a specification
    result = await converter.convert_to_runtime(spec_dict, variables, validation_options)
"""

from .base_converter import (
    RuntimeConverter,
    RuntimeType,
    ConversionMode,
    ConversionResult,
    ComponentCompatibility,
    EdgeValidationResult,
    ValidationOptions,
    ConversionError,
    ConverterValidationError,
    ComponentNotSupportedError
)

from .converter_factory import (
    ConverterFactory,
    ConverterRegistry,
    converter_factory,
    converter_registry,
    register_converter,
    get_converter_factory
)

from .langflow_converter import LangflowConverter
from .temporal_converter import TemporalConverter

__all__ = [
    # Base converter classes
    "RuntimeConverter",
    "RuntimeType",
    "ConversionMode",
    "ConversionResult",
    "ComponentCompatibility",
    "EdgeValidationResult",
    "ValidationOptions",

    # Exceptions
    "ConversionError",
    "ConverterValidationError",
    "ComponentNotSupportedError",

    # Factory and registry
    "ConverterFactory",
    "ConverterRegistry",
    "converter_factory",
    "converter_registry",
    "register_converter",
    "get_converter_factory",

    # Specific converters
    "LangflowConverter",
    "TemporalConverter"
]

# Version info
__version__ = "1.0.0"

# Register the Langflow converter
register_converter(
    RuntimeType.LANGFLOW,
    LangflowConverter,
    {
        "description": "Enhanced Langflow converter with Phase 3 improvements",
        "features": [
            "visual_flow_design",
            "enhanced_validation",
            "performance_optimization",
            "edge_validation"
        ],
        "supported_features": [
            "type_compatibility_validation",
            "comprehensive_edge_validation",
            "performance_optimization",
            "bidirectional_conversion"
        ]
    }
)

# Register the Temporal converter (skeleton for future implementation)
register_converter(
    RuntimeType.TEMPORAL,
    TemporalConverter,
    {
        "description": "Temporal workflow converter (skeleton implementation)",
        "features": [
            "durable_execution",
            "state_persistence",
            "fault_tolerance",
            "long_running_workflows"
        ],
        "supported_features": [
            "workflow_orchestration",
            "retry_policies",
            "state_management",
            "distributed_execution"
        ],
        "implementation_status": "skeleton",
        "estimated_completion": "2-3 weeks"
    }
)