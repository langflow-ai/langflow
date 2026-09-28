"""Exceptions raised by flow operation services."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lfx.services.flow_operations.validation import GraphViolation


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
    """Raised when flow data is malformed or violates graph invariants.

    ``violations`` lists every rule the graph breaks, each with a stable code
    and the path it was found at, so a caller can report all of them at once or
    hand the graph to ``repair_flow_data``.
    """

    code = "FLOW_GRAPH_INVALID"

    def __init__(self, message: str, *, violations: list[GraphViolation] | None = None) -> None:
        super().__init__(message)
        self.violations: list[GraphViolation] = list(violations or [])


class FlowOperationReplayError(FlowOperationError):
    """Raised when derived operations do not replay to the graph they were derived from.

    Every valid transition is expressible in the operation vocabulary, so this
    always means a bug in the diff or the engine, never bad input.
    """

    code = "FLOW_OPERATION_REPLAY_MISMATCH"
