"""
Genesis Multi-Runtime Converter System.

This package provides a comprehensive, extensible architecture for converting
Genesis specifications to multiple runtime environments with bidirectional support.

Key Features:
- Multi-runtime support (Langflow, Temporal, Kafka)
- Bidirectional conversion capabilities
- Plugin architecture for extensibility
- Component gap analysis and mapping
- Runtime registry and factory patterns

Usage:
    from langflow.services.runtime import converter_factory, runtime_registry

    # Create a converter
    converter = converter_factory.create_converter("langflow")

    # Convert specification
    result = converter.convert_to_runtime(genesis_spec)

    # Get available runtimes
    runtimes = runtime_registry.list_available_runtimes()
"""

from .base_converter import (
    RuntimeConverter,
    RuntimeType,
    ConversionMode,
    ConversionError,
    ConverterValidationError,
    ComponentNotSupportedError
)

from .registry import runtime_registry
from .factory import converter_factory

from .langflow_converter import LangflowConverter
from .temporal_converter import TemporalConverter
from .kafka_converter import KafkaConverter
from .gap_analyzer import ConverterGapAnalyzer

__all__ = [
    # Core interfaces and types
    "RuntimeConverter",
    "RuntimeType",
    "ConversionMode",

    # Exceptions
    "ConversionError",
    "ConverterValidationError",
    "ComponentNotSupportedError",

    # Core instances
    "runtime_registry",
    "converter_factory",

    # Converter implementations
    "LangflowConverter",
    "TemporalConverter",
    "KafkaConverter",

    # Tools
    "ConverterGapAnalyzer"
]

# Version info
__version__ = "1.0.0"

# Initialize the runtime system
def initialize_runtime_system():
    """Initialize the multi-runtime converter system."""
    # Register built-in converters
    langflow_converter = LangflowConverter()
    runtime_registry.register_converter(langflow_converter)

    # Register skeleton converters
    temporal_converter = TemporalConverter()
    runtime_registry.register_converter(temporal_converter)

    kafka_converter = KafkaConverter()
    runtime_registry.register_converter(kafka_converter)

    # Auto-discover plugins
    converter_factory.auto_discover_plugins()

# Initialize on import
initialize_runtime_system()