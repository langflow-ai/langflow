"""Server-Sent Events (SSE) formatting helpers."""

import json
from functools import lru_cache

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
    try:
        return _format_progress_event_cached(step, attempt, max_attempts, message, error, class_name, component_code)
    except TypeError:
        # Fallback for unhashable arguments: preserve original behavior
        return _build_event_string(step, attempt, max_attempts, message, error, class_name, component_code)


def format_complete_event(data: dict) -> str:
    """Format SSE complete event."""
    return f"data: {json.dumps({'event': 'complete', 'data': data})}\n\n"


def format_error_event(message: str) -> str:
    """Format SSE error event."""
    return f"data: {json.dumps({'event': 'error', 'message': message})}\n\n"


def format_token_event(chunk: str) -> str:
    """Format SSE token event for streaming LLM output."""
    return f"data: {json.dumps({'event': 'token', 'chunk': chunk})}\n\n"


def _build_event_string(step, attempt, max_attempts, message, error, class_name, component_code) -> str:
    parts = [
        '{"event": "progress", "step": ',
        str(step),
        ', "attempt": ',
        str(attempt),
        ', "max_attempts": ',
        str(max_attempts),
    ]
    if message:
        parts.extend([', "message": ', json.dumps(message)])
    if error:
        parts.extend([', "error": ', json.dumps(error)])
    if class_name:
        parts.extend([', "class_name": ', json.dumps(class_name)])
    if component_code:
        parts.extend([', "component_code": ', json.dumps(component_code)])
    parts.append("}")
    return f"data: {''.join(parts)}\n\n"


@lru_cache(maxsize=2048)
def _format_progress_event_cached(step, attempt, max_attempts, message, error, class_name, component_code) -> str:
    return _build_event_string(step, attempt, max_attempts, message, error, class_name, component_code)
