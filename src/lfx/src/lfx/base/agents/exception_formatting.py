"""Format exceptions to surface useful API error details to the UI.

When an LLM provider raises a structured error (rate limit, auth failure,
quota exceeded), the human-readable explanation lives in attributes like
`.body` (dict) or `.response.json()`, not in `str(exc)`. This helper extracts
that detail so users see *why* their flow failed instead of a generic
"Failure during achat." style message.
"""

from __future__ import annotations

from typing import Any


def format_exception_for_message(exc: BaseException) -> str:
    """Return a user-readable error string for `exc`.

    Combines `str(exc)`, an HTTP status code (if present), and the
    provider-side error message extracted from common API error body shapes
    (IBM watsonx, OpenAI, Anthropic). Designed to never raise — degrades
    gracefully on unexpected attribute shapes.
    """
    main = (str(exc).strip() or type(exc).__name__).rstrip(".")
    parts = [main]

    status = _extract_status_code(exc)
    if status is not None:
        parts.append(f"(HTTP {status})")

    api_message = _extract_api_error_message(exc)
    if api_message and api_message not in main:
        parts.append(f"— {api_message}")

    return " ".join(parts)


def _extract_status_code(exc: BaseException) -> int | None:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None


def _extract_api_error_message(exc: BaseException) -> str | None:
    body = _extract_body(exc)
    if not isinstance(body, dict):
        return None

    # IBM watsonx shape: {"errors": [{"code": "...", "message": "..."}]}
    errors = body.get("errors")
    if isinstance(errors, list):
        msgs = [e.get("message") for e in errors if isinstance(e, dict) and isinstance(e.get("message"), str)]
        if msgs:
            return " | ".join(msgs)

    # OpenAI / Anthropic shape: {"error": {"message": "...", "type": "..."}}
    error = body.get("error")
    if isinstance(error, dict):
        msg = error.get("message")
        if isinstance(msg, str):
            return msg
    if isinstance(error, str):
        return error

    # Some providers put the message at the top level.
    top_message = body.get("message")
    return top_message if isinstance(top_message, str) else None


def _extract_body(exc: BaseException) -> Any:
    body = getattr(exc, "body", None)
    if body is not None:
        return body
    response = getattr(exc, "response", None)
    return _try_json(response)


def _try_json(response: Any) -> Any:
    if response is None:
        return None
    json_method = getattr(response, "json", None)
    if not callable(json_method):
        return None
    try:
        return json_method()
    except Exception:  # noqa: BLE001 — we genuinely don't care why it failed; degrade gracefully
        return None
