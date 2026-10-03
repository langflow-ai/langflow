"""Exceptions raised by flow operation services."""


class FlowOperationError(Exception):
    """Base error for flow operation application."""

    code = "FLOW_OPERATION_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class FlowOperationValidationError(FlowOperationError):
    """Raised when an operation batch is malformed or violates graph invariants."""

    code = "FLOW_OPERATION_INVALID"


class FlowOperationPreconditionError(FlowOperationError):
    """Raised when a write's ``expect`` does not hold on the graph it is applied to.

    The operation itself is well formed; the graph changed since the writer
    read it. The whole batch is refused, so the writer can re-read and retry.
    """

    code = "EXPECTATION_FAILED"


class FlowDataValidationError(FlowOperationError):
    """Raised when persisted flow data is malformed or violates graph invariants."""

    code = "FLOW_GRAPH_INVALID"
