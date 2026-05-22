"""Custom exception types for Langflow integration."""


class LangflowIntegrationError(Exception):
    """Base exception for Langflow integration errors."""

    pass


class ConversionError(LangflowIntegrationError):
    """Error during Langflow to Stepflow conversion."""

    pass


class ValidationError(LangflowIntegrationError):
    """Error during workflow validation."""

    pass


class ExecutionError(LangflowIntegrationError):
    """Error during component execution."""

    pass
