"""Server-Sent Events (SSE) formatting helpers."""

import json


def format_progress_event(step: str, attempt: int, max_attempts: int) -> str:
    """Format SSE progress event."""
    data = {"event": "progress", "step": step, "attempt": attempt, "max_attempts": max_attempts}
    return f"data: {json.dumps(data)}\n\n"


def format_complete_event(data: dict) -> str:
    """Format SSE complete event."""
    return f"data: {json.dumps({'event': 'complete', 'data': data})}\n\n"


def format_error_event(message: str) -> str:
    """Format SSE error event."""
    return f"data: {json.dumps({'event': 'error', 'message': message})}\n\n"
