"""Client-facing error policy for owner and delegated workflow execution."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

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
    if isinstance(error, HTTPException):
        return HTTPException(
            status_code=error.status_code,
            detail=SAFE_WORKFLOW_ERROR_MESSAGE,
            headers=error.headers,
        )
    return RuntimeError(SAFE_WORKFLOW_ERROR_MESSAGE)


def caller_owns_flow(flow: object, user: object) -> bool:
    """Return whether the request actor and stored flow owner are the same principal."""
    flow_user_id = getattr(flow, "user_id", None)
    user_id = getattr(user, "id", None)
    return flow_user_id is not None and user_id is not None and str(flow_user_id) == str(user_id)
