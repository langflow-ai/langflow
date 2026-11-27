"""Exceptions raised by flow operation services."""


class FlowOperationError(Exception):
    """Base error for flow operation application."""

    code = "FLOW_OPERATION_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class FlowOperationValidationError(FlowOperationError):
    """Raised when an operation batch is malformed or violates graph invariants.

    An edge rule error names the edge that broke the rule in ``edge_id``.
    Checking one edge can find another one broken (an edge into the same input
    whose handles do not read), so that is not always the edge being checked.
    """

    code = "FLOW_OPERATION_INVALID"

    def __init__(self, message: str, *, code: str | None = None, edge_id: str | None = None) -> None:
        super().__init__(message, code=code)
        self.edge_id = edge_id


class FlowDataValidationError(FlowOperationError):
    """Raised when persisted flow data is malformed or violates graph invariants."""

    code = "FLOW_GRAPH_INVALID"
