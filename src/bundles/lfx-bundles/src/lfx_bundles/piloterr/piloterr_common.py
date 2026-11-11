"""Shared HTTP plumbing for the Piloterr components.

Piloterr is a web data API. Every component calls the fixed host
``https://api.piloterr.com`` with the API key in the ``x-api-key`` header.
"""

from __future__ import annotations

from typing import Any

import httpx

API_BASE_URL = "https://api.piloterr.com"
DOCUMENTATION_URL = "https://docs.piloterr.com"
API_KEY_INFO = "Your Piloterr API key, from https://app.piloterr.com."  # pragma: allowlist secret

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
_STATUS_LABELS = {
    401: "Piloterr rejected the API key (401)",
    402: "Piloterr account is out of credits (402)",
    429: "Piloterr rate limit exceeded (429)",
}
# Piloterr reports a rate limit as 401 "Rate limit exceeded", not 429.
_RATE_LIMIT_401_LABEL = "Piloterr rate limit exceeded (401)"


class PiloterrAPIError(Exception):
    """A Piloterr request failed; the message is safe to show in the component output."""


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
            error = body.get("error") or body.get("message") or ""
            if isinstance(error, dict):
                error = error.get("message") or ""
            detail = str(error)
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    detail = _redact(detail, api_key)[:_ERROR_DETAIL_LIMIT]
    if response.status_code == httpx.codes.UNAUTHORIZED and "rate limit" in detail.lower():
        label = _RATE_LIMIT_401_LABEL
    else:
        label = _STATUS_LABELS.get(response.status_code, f"Piloterr API error ({response.status_code})")
    return f"{label}: {detail}" if detail else label


def piloterr_get(path: str, *, api_key: Any, params: dict[str, Any], timeout: float) -> httpx.Response:
    """GET ``path`` on the Piloterr API and return the successful response.

    Raises:
        PiloterrAPIError: On a missing key, a transport error, or a non-2xx status.
    """
    key = secret_value(api_key)
    if not key:
        msg = "Enter a Piloterr API key."
        raise PiloterrAPIError(msg)
    headers = {"x-api-key": key, "Accept": "application/json"}
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request("GET", f"{API_BASE_URL}{path}", params=params, headers=headers)
    except httpx.TimeoutException as exc:
        msg = f"Piloterr request timed out after {timeout:g} seconds."
        raise PiloterrAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach the Piloterr API: {type(exc).__name__}: {_redact(str(exc), key)}"
        raise PiloterrAPIError(msg) from exc
    if not response.is_success:
        raise PiloterrAPIError(_error_message(response, key))
    return response


def json_object(response: httpx.Response) -> dict[str, Any]:
    """Return the body as a JSON object.

    Raises:
        PiloterrAPIError: If the body is not JSON or not an object.
    """
    try:
        body = response.json()
    except ValueError as exc:
        msg = "Piloterr API returned a response that is not JSON."
        raise PiloterrAPIError(msg) from exc
    if not isinstance(body, dict):
        msg = "Piloterr API returned an unexpected response shape."
        raise PiloterrAPIError(msg)
    return body


def page_html(response: httpx.Response) -> str:
    """Return the page HTML of a website endpoint.

    Piloterr answers with the HTML as a JSON string; a raw HTML body is accepted too.

    Raises:
        PiloterrAPIError: If the JSON body is not a string.
    """
    try:
        body = response.json()
    except ValueError:
        return response.text
    if not isinstance(body, str):
        msg = "Piloterr API returned an unexpected response shape; expected the page HTML."
        raise PiloterrAPIError(msg)
    return body
