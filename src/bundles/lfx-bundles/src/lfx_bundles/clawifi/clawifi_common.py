"""Shared HTTP plumbing for the Clawifi components.

Clawifi is web access for AI agents: it searches many engines as one, reads pages
and PDFs, and returns the passages that answer a question, each with its source.
Every component calls the fixed host ``https://api.clawifi.dev`` with the API key
as a Bearer token.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx

API_BASE_URL = "https://api.clawifi.dev"
DOCUMENTATION_URL = "https://clawifi.dev/docs"
SIGNUP_URL = "https://clawifi.dev/signup"
DEFAULT_TIMEOUT_SECONDS = 60.0

API_KEY_INFO = f"Your Clawifi API key. Create one at {SIGNUP_URL}."

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
_STATUS_LABELS = {
    401: "Clawifi rejected the API key (401)",
    402: "Not enough Clawifi credits for this call (402)",
    403: "Clawifi refused the request (403)",
    429: "Clawifi rate limit exceeded (429)",
}


class ClawifiAPIError(Exception):
    """A Clawifi request failed; the message is safe to show in the component output."""


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def split_list(value: Any) -> list[str]:
    """Split a comma- or newline-separated input into a list of non-empty strings."""
    if isinstance(value, (list, tuple)):
        items = [str(item) for item in value]
    else:
        items = str(value or "").replace("\n", ",").split(",")
    return [item.strip() for item in items if item.strip()]


def require_http_url(value: Any) -> str:
    """Return the stripped URL, or raise when it is not an absolute http(s) URL."""
    url = str(value or "").strip()
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
    except ValueError:  # e.g. an unmatched bracket in the host
        valid = False
    if not valid:
        msg = f"Enter an absolute http(s) URL, such as https://example.com; got {url!r}."
        raise ClawifiAPIError(msg)
    return url


def error_messages(errors: Any) -> str:
    """Join the ``message`` of each entry in a response's ``errors`` list."""
    if not isinstance(errors, list):
        return ""
    messages = []
    for error in errors:
        if isinstance(error, dict):
            text = str(error.get("message") or error.get("code") or "").strip()
        else:
            text = str(error or "").strip()
        if text:
            messages.append(text)
    return "; ".join(messages)


def _redact(text: str, api_key: str) -> str:
    """Replace the API key in text with ***."""
    return text.replace(api_key, "***") if api_key else text


def _error_detail(body: Any) -> str:
    """Pull the human-readable message out of a Clawifi error body.

    Errors look like ``{"detail": "...", "error": {"code": "...", "message": "..."}}``;
    ``detail`` is a list instead of a string for request validation errors.
    """
    if not isinstance(body, dict):
        return ""
    error = body.get("error")
    if isinstance(error, dict):
        message = str(error.get("message") or "").strip()
        code = str(error.get("code") or "").strip()
        if message and code and code != "http_error":
            return f"{message} ({code})"
        if message or code:
            return message or code
    detail = body.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        return error_messages([{"message": item.get("msg")} if isinstance(item, dict) else item for item in detail])
    return str(body.get("message") or "")


def _error_message(response: httpx.Response, api_key: str) -> str:
    """Build a short, key-free error message from a failed API response."""
    try:
        detail = _error_detail(response.json())
    except ValueError:
        detail = response.text.strip()
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    detail = _redact(detail, api_key)[:_ERROR_DETAIL_LIMIT]
    label = _STATUS_LABELS.get(response.status_code, f"Clawifi API error ({response.status_code})")
    message = f"{label}: {detail}" if detail else label
    retry_after = response.headers.get("Retry-After", "").strip()
    if response.status_code == httpx.codes.TOO_MANY_REQUESTS and retry_after.isdigit():
        message = f"{message.rstrip('.')}. Retry after {retry_after} seconds."
    return message


def clawifi_post(path: str, *, api_key: Any, timeout: float, json: dict[str, Any]) -> dict[str, Any]:
    """POST a JSON body to the Clawifi API and return the JSON response.

    Raises:
        ClawifiAPIError: On a missing key, a transport error, a non-2xx status, or a body that is not a JSON object.
    """
    key = secret_value(api_key)
    if not key:
        msg = f"Enter a Clawifi API key. Create one at {SIGNUP_URL}."
        raise ClawifiAPIError(msg)
    headers = {"Authorization": f"Bearer {key}"}
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request("POST", f"{API_BASE_URL}{path}", json=json, headers=headers)
    except httpx.TimeoutException as exc:
        msg = f"Clawifi request timed out after {timeout:g} seconds."
        raise ClawifiAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach the Clawifi API: {type(exc).__name__}: {_redact(str(exc), key)}"
        raise ClawifiAPIError(msg) from exc
    if not response.is_success:
        raise ClawifiAPIError(_error_message(response, key))
    try:
        body = response.json()
    except ValueError as exc:
        msg = "Clawifi API returned a response that is not JSON."
        raise ClawifiAPIError(msg) from exc
    if not isinstance(body, dict):
        msg = "Clawifi API returned an unexpected response shape."
        raise ClawifiAPIError(msg)
    return body
