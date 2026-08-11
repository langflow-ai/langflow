"""Client-facing error policy for owner and delegated workflow execution."""

from __future__ import annotations

from dataclasses import dataclass

SAFE_WORKFLOW_ERROR_MESSAGE = "Workflow execution failed."


@dataclass(frozen=True, slots=True)
class ExecutionErrorDetails:
    """The error fields that may cross an execution API boundary."""

    message: str
    stack_trace: str


def error_details_for_client(
    error: Exception,
    *,
    expose_details: bool,
    message: str | None = None,
    stack_trace: str | None = None,
) -> ExecutionErrorDetails:
    """Keep owner diagnostics while removing delegated/public runtime details."""
    if expose_details:
        return ExecutionErrorDetails(
            message=message if message is not None else str(error),
            stack_trace=stack_trace or "",
        )
    return ExecutionErrorDetails(message=SAFE_WORKFLOW_ERROR_MESSAGE, stack_trace="")


def error_for_client(error: Exception, *, expose_details: bool) -> Exception:
    """Return an exception suitable for serializers that accept an exception object."""
    if expose_details:
        return error
    return RuntimeError(SAFE_WORKFLOW_ERROR_MESSAGE)
