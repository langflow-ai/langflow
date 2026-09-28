"""Exceptions raised by flow operation services."""


class FlowOperationError(Exception):
    """Base error for flow operation application."""


class FlowOperationValidationError(FlowOperationError):
    """Raised when an operation batch is malformed or violates graph invariants."""


class FlowDataValidationError(FlowOperationError):
    """Raised when persisted flow data is malformed or violates graph invariants."""
