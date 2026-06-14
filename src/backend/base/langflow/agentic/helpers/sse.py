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


def format_flow_update_event(update: dict) -> str:
    """Format SSE flow_update event for real-time canvas changes."""
    return f"data: {json.dumps({'event': 'flow_update', **update})}\n\n"


def format_cancelled_event() -> str:
    """Format SSE cancelled event when client disconnects."""
    return f"data: {json.dumps({'event': 'cancelled', 'message': 'Generation cancelled by user'})}\n\n"


_DRIVE_LETTER_PREFIX_LEN = 2


def format_file_written_event(
    *,
    action: str,
    path: str,
    size: int,
    content: str | None = None,
) -> str:
    """Format SSE file_written event for sandboxed filesystem writes.

    Emitted by ``assistant_service`` between LLM tokens when the agent's
    ``write_file`` or ``edit_file`` tool ran successfully. The frontend uses
    these to render a per-file card with Open/Download actions — and, when
    ``content`` is provided, renders the body inline without a second HTTP
    round-trip.

    Security: refuses absolute paths or Windows drive letters so a misbehaving
    upstream cannot leak ``BASE_DIR`` to the SSE consumer. This is the second
    enforcement point — the first is ``emit_file_event`` at the queue boundary.
    """
    if not path:
        msg = "format_file_written_event: path must be non-empty"
        raise ValueError(msg)
    if path.startswith(("/", "\\")):
        msg = f"format_file_written_event: path must be relative, got absolute: {path!r}"
        raise ValueError(msg)
    if len(path) >= _DRIVE_LETTER_PREFIX_LEN and path[1] == ":" and path[0].isalpha():
        msg = f"format_file_written_event: path must be relative, got drive-letter: {path!r}"
        raise ValueError(msg)
    payload: dict[str, object] = {
        "event": "file_written",
        "action": action,
        "path": path,
        "size": size,
    }
    if content is not None:
        payload["content"] = content
    return f"data: {json.dumps(payload)}\n\n"


def format_flow_preview_event(
    flow_data: dict,
    name: str = "",
    node_count: int = 0,
    edge_count: int = 0,
    graph: str = "",
) -> str:
    """Format SSE flow_preview event with the built flow data.

    The frontend can use this to render a preview of the flow
    without saving it to the server.
    """
    payload = {
        "event": "flow_preview",
        "flow": flow_data,
        "name": name,
        "node_count": node_count,
        "edge_count": edge_count,
        "graph": graph,
    }
    return f"data: {json.dumps(payload)}\n\n"
