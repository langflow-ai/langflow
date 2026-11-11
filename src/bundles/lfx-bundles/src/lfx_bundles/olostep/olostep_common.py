"""Shared HTTP plumbing for the Olostep components.

Olostep is web data infrastructure for AI agents: live web search, scraping,
crawling, site maps and cited answers. Every component calls the fixed host
``https://api.olostep.com`` with the API key as a Bearer token.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx

API_BASE_URL = "https://api.olostep.com"
DOCUMENTATION_URL = "https://docs.olostep.com"
DEFAULT_TIMEOUT_SECONDS = 60.0

API_KEY_INFO = "Your Olostep API key. Create one at https://www.olostep.com/dashboard/api-keys."

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
_STATUS_LABELS = {
    401: "Olostep rejected the API key (401)",
    402: "Olostep rejected the request: invalid API key or no credits left (402)",
    429: "Olostep rate limit exceeded (429)",
}


class OlostepAPIError(Exception):
    """An Olostep request failed; the message is safe to show in the component output."""


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
        raise OlostepAPIError(msg)
    return url


def _redact(text: str, api_key: str) -> str:
    """Replace the API key in text with ***."""
    return text.replace(api_key, "***") if api_key else text


def _error_detail(body: Any) -> str:
    """Pull the human-readable message out of the error shapes the API returns."""
    if not isinstance(body, dict):
        return ""
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("type") or "")
    return str(body.get("detail") or body.get("message") or error or body.get("title") or "")


def _error_message(response: httpx.Response, api_key: str) -> str:
    """Build a short, key-free error message from a failed API response."""
    try:
        detail = _error_detail(response.json())
    except ValueError:
        detail = response.text.strip()
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    detail = _redact(detail, api_key)[:_ERROR_DETAIL_LIMIT]
    label = _STATUS_LABELS.get(response.status_code, f"Olostep API error ({response.status_code})")
    return f"{label}: {detail}" if detail else label


def olostep_request(
    method: str,
    path: str,
    *,
    api_key: Any,
    timeout: float,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call the Olostep API and return the JSON body.

    Raises:
        OlostepAPIError: On a missing key, a transport error, a non-2xx status, or a body that is not a JSON object.
    """
    key = secret_value(api_key)
    if not key:
        msg = "Enter an Olostep API key. Create one at https://www.olostep.com/dashboard/api-keys."
        raise OlostepAPIError(msg)
    headers = {"Authorization": f"Bearer {key}"}
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request(method, f"{API_BASE_URL}{path}", params=params, json=json, headers=headers)
    except httpx.TimeoutException as exc:
        msg = f"Olostep request timed out after {timeout:g} seconds."
        raise OlostepAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach the Olostep API: {type(exc).__name__}: {_redact(str(exc), key)}"
        raise OlostepAPIError(msg) from exc
    if not response.is_success:
        raise OlostepAPIError(_error_message(response, key))
    try:
        body = response.json()
    except ValueError as exc:
        msg = "Olostep API returned a response that is not JSON."
        raise OlostepAPIError(msg) from exc
    if not isinstance(body, dict):
        msg = "Olostep API returned an unexpected response shape."
        raise OlostepAPIError(msg)
    return body
