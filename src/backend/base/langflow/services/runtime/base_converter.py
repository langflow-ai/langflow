"""
Abstract Base Converter Interface for Multi-Runtime Support.

This module provides the foundation for the pluggable converter architecture
that supports multiple runtime environments (Langflow, Temporal, Kafka, etc.)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Protocol, runtime_checkable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RuntimeType(Enum):
    """Supported runtime types."""
    LANGFLOW = "langflow"
    TEMPORAL = "temporal"
    KAFKA = "kafka"
    GENERIC = "generic"


class ConversionMode(Enum):
    """Conversion direction modes."""
    SPEC_TO_RUNTIME = "spec_to_runtime"
    RUNTIME_TO_SPEC = "runtime_to_spec"


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
    Abstract base class for all runtime converters.

    This interface defines the contract that all runtime converters must implement
    to support the Genesis multi-runtime architecture.
    """

    def __init__(self, runtime_type: RuntimeType):
        """
        Initialize the runtime converter.

        Args:
            runtime_type: The type of runtime this converter supports
        """
        self.runtime_type = runtime_type
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

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
    async def convert_to_runtime(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Genesis specification to runtime-specific format.

        Args:
            spec: Genesis specification dictionary

        Returns:
            Runtime-specific configuration/workflow definition

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

    async def convert(self, data: Dict[str, Any], mode: ConversionMode) -> Dict[str, Any]:
        """
        Generic conversion method that dispatches to appropriate converter.

        Args:
            data: Data to convert
            mode: Conversion direction

        Returns:
            Converted data

        Raises:
            ConversionError: If conversion fails
            ValueError: If mode is not supported
        """
        if not self.validate_conversion_mode(mode):
            raise ValueError(f"Conversion mode {mode.value} not supported by {self.runtime_type.value}")

        if mode == ConversionMode.SPEC_TO_RUNTIME:
            return await self.convert_to_runtime(data)
        elif mode == ConversionMode.RUNTIME_TO_SPEC:
            return await self.convert_from_runtime(data)
        else:
            raise ValueError(f"Unknown conversion mode: {mode.value}")


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