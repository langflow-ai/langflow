"""Shared HTTP plumbing for the Autom components.

Autom is a SERP API that returns live search engine results as JSON. Every
component calls the fixed host ``https://api.autom.dev`` with the API key in the
``x-api-key`` header.
"""

from __future__ import annotations

from typing import Any

import httpx

API_BASE_URL = "https://api.autom.dev"
DOCUMENTATION_URL = "https://docs.autom.dev"
DEFAULT_TIMEOUT_SECONDS = 60.0
API_KEY_INFO = "Your Autom API key, from https://app.autom.dev."  # pragma: allowlist secret
COUNTRY_INFO = "Two-letter country code to search from, such as us or fr."
LANGUAGE_INFO = "Language code of the results, such as en or fr."

# Google returns about 10 organic results per page.
MAX_RESULTS_LIMIT = 10

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
_STATUS_LABELS = {
    401: "Autom rejected the API key (401)",
    402: "Autom account is out of credits (402)",
    429: "Autom rate limit exceeded (429)",
}
# Autom reports a rate limit as 401 "Rate limit exceeded", not 429.
_RATE_LIMIT_401_LABEL = "Autom rate limit exceeded (401)"


class AutomAPIError(Exception):
    """An Autom request failed; the message is safe to show in the component output."""


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def clamp_max_results(value: Any) -> int:
    """Return ``value`` as an int between 1 and ``MAX_RESULTS_LIMIT`` (5 when unset or invalid)."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 5
    return min(max(number, 1), MAX_RESULTS_LIMIT)


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
    if response.status_code == httpx.codes.UNAUTHORIZED and "rate limit" in detail.lower():
        label = _RATE_LIMIT_401_LABEL
    else:
        label = _STATUS_LABELS.get(response.status_code, f"Autom API error ({response.status_code})")
    return f"{label}: {detail}" if detail else label


def autom_get(path: str, *, api_key: Any, params: dict[str, Any], timeout: float) -> dict[str, Any]:
    """GET ``path`` on the Autom API and return the JSON body.

    Raises:
        AutomAPIError: On a missing key, a transport error, a non-2xx status, or a body that is not a JSON object.
    """
    key = secret_value(api_key)
    if not key:
        msg = "Enter an Autom API key."
        raise AutomAPIError(msg)
    headers = {"x-api-key": key, "Accept": "application/json"}
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request("GET", f"{API_BASE_URL}{path}", params=params, headers=headers)
    except httpx.TimeoutException as exc:
        msg = f"Autom request timed out after {timeout:g} seconds."
        raise AutomAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach the Autom API: {type(exc).__name__}: {_redact(str(exc), key)}"
        raise AutomAPIError(msg) from exc
    if not response.is_success:
        raise AutomAPIError(_error_message(response, key))
    try:
        body = response.json()
    except ValueError as exc:
        msg = "Autom API returned a response that is not JSON."
        raise AutomAPIError(msg) from exc
    if not isinstance(body, dict):
        msg = "Autom API returned an unexpected response shape."
        raise AutomAPIError(msg)
    return body


def organic_rows(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the object rows of ``organic_results`` (missing means no results).

    Raises:
        AutomAPIError: If ``organic_results`` is present but is not a list.
    """
    rows = body.get("organic_results")
    if rows is None:
        return []
    if not isinstance(rows, list):
        msg = "Autom API returned organic_results that is not a list."
        raise AutomAPIError(msg)
    return [row for row in rows if isinstance(row, dict)]
