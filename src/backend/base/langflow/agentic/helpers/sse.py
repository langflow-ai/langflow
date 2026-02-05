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
    class_name: str | None = None,
    component_code: str | None = None,
) -> str:
    """Format SSE progress event.

    Args:
        step: The current step in the process
        attempt: Current attempt number (1-indexed)
        max_attempts: Maximum number of attempts
        message: Optional human-readable message
        error: Optional error message (for validation_failed step)
        class_name: Optional class name (for validation_failed step)
        component_code: Optional component code (for validation_failed step)
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
    if class_name:
        data["class_name"] = class_name
    if component_code:
        data["component_code"] = component_code
    return f"data: {json.dumps(data)}\n\n"


def format_complete_event(data: dict) -> str:
    """Format SSE complete event."""
    return f"data: {json.dumps({'event': 'complete', 'data': data})}\n\n"


def format_error_event(message: str) -> str:
    """Format SSE error event."""
    return f"data: {json.dumps({'event': 'error', 'message': message})}\n\n"


def format_token_event(chunk: str) -> str:
    """Format SSE token event for streaming LLM output."""
    return f"data: {json.dumps({'event': 'token', 'chunk': chunk})}\n\n"


def format_cancelled_event() -> str:
    """Format SSE cancelled event when client disconnects."""
    return f"data: {json.dumps({'event': 'cancelled'})}\n\n"
