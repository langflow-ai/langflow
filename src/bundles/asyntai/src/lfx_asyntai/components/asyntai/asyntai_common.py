"""Shared HTTP helper for the Asyntai components.

All three components call the Asyntai public REST API
(https://asyntai.com/documentation/api-reference/) with one API key, so the
request, the authentication header and the error messages live here once.
"""

from __future__ import annotations

from typing import Any

import httpx

API_BASE_URL = "https://asyntai.com/api/v1"
REQUEST_TIMEOUT = 60
USER_AGENT = "langflow-asyntai-bundle"
KEY_HELP = "Create a key in the Asyntai dashboard under Settings -> API."


class AsyntaiAPIError(Exception):
    """The Asyntai API refused the request or could not be reached."""


def _error_from_response(response: httpx.Response, payload: Any) -> str:
    """Turn a failed response into one readable sentence."""
    detail = payload.get("error") if isinstance(payload, dict) else None
    if response.status_code == httpx.codes.UNAUTHORIZED:
        return f"Asyntai rejected the API key. {KEY_HELP}"
    if response.status_code == httpx.codes.FORBIDDEN:
        return detail or "The Asyntai API needs a paid plan. See https://asyntai.com/pricing/."
    if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
        return detail or "The Asyntai message limit for this month is reached."
    return detail or f"Asyntai API error {response.status_code}."


def asyntai_request(
    method: str,
    path: str,
    api_key: str | None,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call ``API_BASE_URL + path`` and return the decoded JSON body.

    Raises ``AsyntaiAPIError`` with a plain message for every failure, so the
    components can show it to the user as a single result row.
    """
    if not api_key:
        msg = f"An Asyntai API key is required. {KEY_HELP}"
        raise AsyntaiAPIError(msg)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    try:
        response = httpx.request(
            method,
            f"{API_BASE_URL}{path}",
            headers=headers,
            params=params,
            json=json_body,
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        msg = f"Could not reach the Asyntai API: {exc}"
        raise AsyntaiAPIError(msg) from exc

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if response.is_error:
        raise AsyntaiAPIError(_error_from_response(response, payload))
    if not isinstance(payload, dict):
        msg = f"Asyntai returned an unexpected response (HTTP {response.status_code})."
        raise AsyntaiAPIError(msg)
    if payload.get("success") is False:
        raise AsyntaiAPIError(payload.get("error") or "The Asyntai API reported an error.")
    return payload


def clean_text(value: Any) -> str:
    """Return a stripped string for an optional text input, or an empty string."""
    return value.strip() if isinstance(value, str) else ""
