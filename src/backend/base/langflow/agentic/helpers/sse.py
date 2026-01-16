"""Server-Sent Events (SSE) formatting helpers."""

import json

from langflow.agentic.api.schemas import StepType


def format_progress_event(
    step: StepType,
    attempt: int,
    max_attempts: int,
    *,
    message: str | None = None,
    error: str | None = None,
) -> str:
    """Format SSE progress event.

    Args:
        step: The current step in the process
        attempt: Current attempt number (1-indexed)
        max_attempts: Maximum number of attempts
        message: Optional human-readable message
        error: Optional error message (for validation_failed step)
    """
    data: dict = {
        "event": "progress",
        "step": step,
        "attempt": attempt,
        "max_attempts": max_attempts,
    }
    if message:
        data["message"] = message
    if error:
        data["error"] = error
    return f"data: {json.dumps(data)}\n\n"


def format_complete_event(data: dict) -> str:
    """Format SSE complete event."""
    return f"data: {json.dumps({'event': 'complete', 'data': data})}\n\n"


def format_error_event(message: str) -> str:
    """Format SSE error event."""
    return f"data: {json.dumps({'event': 'error', 'message': message})}\n\n"
