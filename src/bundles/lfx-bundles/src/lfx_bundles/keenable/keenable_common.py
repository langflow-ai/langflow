"""Shared HTTP plumbing for the Keenable components.

Keenable is a web search and page fetch API built for AI agents. Both components
call the fixed host ``https://api.keenable.ai``. Without an API key they use the
keyless public endpoints, which identify the calling app through the
``X-Keenable-Title`` header. With a key they use the keyed endpoints, which take
it as ``X-API-Key`` and lift the keyless rate limits.
"""

from __future__ import annotations

from typing import Any

import httpx

API_BASE_URL = "https://api.keenable.ai"
DOCUMENTATION_URL = "https://docs.keenable.ai"
APP_TITLE = "Langflow"
DEFAULT_TIMEOUT_SECONDS = 30.0

API_KEY_INFO = (
    "Optional. Leave empty to use the keyless public endpoint. A Keenable API key lifts the keyless rate limits."
)

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
_STATUS_LABELS = {
    401: "Keenable rejected the API key (401)",
    402: "Keenable account is out of credits (402)",
    429: "Keenable rate limit exceeded (429); an API key lifts the keyless limits",
}


class KeenableAPIError(Exception):
    """A Keenable request failed; the message is safe to show in the component output."""


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def _redact(text: str, api_key: str) -> str:
    return text.replace(api_key, "***") if api_key else text


def _error_message(response: httpx.Response, api_key: str) -> str:
    detail = ""
    try:
        body = response.json()
    except ValueError:
        detail = response.text.strip()
    else:
        if isinstance(body, dict):
            detail = str(body.get("message") or body.get("error") or "")
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    detail = _redact(detail, api_key)[:_ERROR_DETAIL_LIMIT]
    label = _STATUS_LABELS.get(response.status_code, f"Keenable API error ({response.status_code})")
    return f"{label}: {detail}" if detail else label


def keenable_request(
    method: str,
    public_path: str,
    keyed_path: str,
    *,
    api_key: Any,
    timeout: float,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call the keyed endpoint when a key is set, else the keyless one, and return the JSON body.

    Raises:
        KeenableAPIError: On a transport error, a non-2xx status, or a body that is not a JSON object.
    """
    key = secret_value(api_key)
    headers = {"X-Keenable-Title": APP_TITLE}
    if key:
        headers["X-API-Key"] = key
    url = f"{API_BASE_URL}{keyed_path if key else public_path}"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request(method, url, params=params, json=json, headers=headers)
    except httpx.TimeoutException as exc:
        msg = f"Keenable request timed out after {timeout:g} seconds."
        raise KeenableAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach the Keenable API: {type(exc).__name__}: {_redact(str(exc), key)}"
        raise KeenableAPIError(msg) from exc
    if not response.is_success:
        raise KeenableAPIError(_error_message(response, key))
    try:
        body = response.json()
    except ValueError as exc:
        msg = "Keenable API returned a response that is not JSON."
        raise KeenableAPIError(msg) from exc
    if not isinstance(body, dict):
        msg = "Keenable API returned an unexpected response shape."
        raise KeenableAPIError(msg)
    return body
