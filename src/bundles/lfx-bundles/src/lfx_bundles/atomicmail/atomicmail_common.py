"""Shared HTTP plumbing for the Atomic Mail components.

Atomic Mail gives an AI agent an email inbox of its own. Every component sends one
request to the fixed host ``https://mcp.atomicmail.ai`` with the inbox API key as a
Bearer token. The endpoint speaks JSON-RPC: the request names one mail action
(``send_email``, ``read_inbox``, ``search_messages`` or ``read_message``) and the
answer carries a ``structuredContent`` object, or ``isError`` with a message.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

API_URL = "https://mcp.atomicmail.ai/mcp"
DOCUMENTATION_URL = "https://docs.atomicmail.ai"
DASHBOARD_URL = "https://dashboard.atomicmail.ai"
DEFAULT_TIMEOUT_SECONDS = 30.0

API_KEY_INFO = (
    f"The API key of your Atomic Mail inbox. Create an inbox at {DASHBOARD_URL} to get one."  # pragma: allowlist secret
)

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
_STATUS_LABELS = {
    401: f"Atomic Mail rejected the API key (401). Check the key at {DASHBOARD_URL}",
    403: "Atomic Mail refused the request (403)",
    429: "Atomic Mail rate limit reached (429). Wait a minute and try again",
}


class AtomicMailAPIError(Exception):
    """An Atomic Mail request failed; the message is safe to show in the component output."""


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def split_addresses(value: Any) -> list[str]:
    """Split a comma, semicolon or newline separated string into trimmed email addresses."""
    text = str(value or "").replace(";", ",").replace("\n", ",")
    return [part.strip() for part in text.split(",") if part.strip()]


def format_people(value: Any) -> str:
    """Render a list of ``{"name", "email"}`` objects as ``a@example.com, b@example.com``."""
    rows = value if isinstance(value, list) else []
    return ", ".join(str(row.get("email") or "") for row in rows if isinstance(row, dict) and row.get("email"))


def _redact(text: str, api_key: str) -> str:
    """Replace the API key in text with ***."""
    return text.replace(api_key, "***") if api_key else text


def _clip(text: str, api_key: str) -> str:
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    return _redact(text.strip(), api_key)[:_ERROR_DETAIL_LIMIT]


def _http_error_message(response: httpx.Response, api_key: str) -> str:
    """Build a short, key-free error message from a non-2xx response."""
    label = _STATUS_LABELS.get(response.status_code)
    if label:
        return f"{label}."
    detail = ""
    try:
        body = response.json()
    except ValueError:
        detail = response.text
    else:
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                detail = str(error.get("message") or "")
            else:
                detail = str(body.get("error_description") or error or "")
    detail = _clip(detail, api_key)
    label = f"Atomic Mail API error ({response.status_code})"
    return f"{label}: {detail}" if detail else f"{label}."


def _parse_body(response: httpx.Response) -> dict[str, Any]:
    """Return the JSON-RPC message of a response sent as JSON or as a one-event stream."""
    text = response.text
    if "text/event-stream" in response.headers.get("content-type", ""):
        text = "\n".join(line[5:].strip() for line in text.splitlines() if line.startswith("data:"))
    try:
        body = json.loads(text)
    except ValueError as exc:
        msg = "Atomic Mail returned a response that is not JSON."
        raise AtomicMailAPIError(msg) from exc
    if not isinstance(body, dict):
        msg = "Atomic Mail returned an answer in an unexpected shape."
        raise AtomicMailAPIError(msg)
    return body


async def atomicmail_call(
    action: str,
    arguments: dict[str, Any],
    *,
    api_key: Any,
    timeout: float,
) -> dict[str, Any]:
    """Run one Atomic Mail action and return its result object.

    Empty arguments are left out of the request.

    Raises:
        AtomicMailAPIError: On a missing key, a transport error, a non-2xx status,
            an answer that is not JSON, or an action that Atomic Mail refused.
    """
    key = secret_value(api_key)
    if not key:
        msg = f"Enter an Atomic Mail API key. Create an inbox at {DASHBOARD_URL} to get one."
        raise AtomicMailAPIError(msg)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": action,
            "arguments": {name: value for name, value in arguments.items() if value not in (None, "", [])},
        },
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                API_URL,
                json=payload,
                headers={
                    "authorization": f"Bearer {key}",
                    "accept": "application/json, text/event-stream",
                },
            )
    except httpx.TimeoutException as exc:
        msg = f"Atomic Mail did not answer within {timeout:g} seconds."
        raise AtomicMailAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach Atomic Mail: {type(exc).__name__}: {_clip(str(exc), key)}"
        raise AtomicMailAPIError(msg) from exc
    if not response.is_success:
        raise AtomicMailAPIError(_http_error_message(response, key))

    body = _parse_body(response)
    error = body.get("error")
    if error:
        detail = error.get("message") if isinstance(error, dict) else error
        msg = f"Atomic Mail refused the request: {_clip(str(detail or ''), key)}"
        raise AtomicMailAPIError(msg)
    result = body.get("result")
    if not isinstance(result, dict):
        msg = "Atomic Mail returned an answer without a result."
        raise AtomicMailAPIError(msg)

    content = result.get("content")
    first = content[0] if isinstance(content, list) and content else None
    text = str(first.get("text") or "") if isinstance(first, dict) else ""
    if result.get("isError"):
        raise AtomicMailAPIError(_clip(text, key) or "Atomic Mail refused the request.")
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    return {"text": text}
