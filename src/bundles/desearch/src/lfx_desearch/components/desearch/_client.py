"""Shared HTTP helpers for the Desearch components.

The Desearch API (https://api.desearch.ai) takes the API key as the raw value of
the ``Authorization`` header, with no ``Bearer`` prefix.
"""

import httpx

API_BASE = "https://api.desearch.ai"
USER_AGENT = "langflow-desearch-bundle"
KEY_REQUIRED = "Desearch API key is required. Set the Desearch API Key input."


def desearch_request(method: str, path: str, api_key: str, *, params=None, json=None, timeout: float = 60):
    """Call the Desearch API and return the decoded JSON payload."""
    if not api_key:
        raise ValueError(KEY_REQUIRED)
    headers = {"Authorization": api_key, "Accept": "application/json", "User-Agent": USER_AGENT}
    response = httpx.request(method, API_BASE + path, headers=headers, params=params, json=json, timeout=timeout)
    response.raise_for_status()
    return response.json()


def http_error_message(error: httpx.HTTPStatusError) -> str:
    """Describe a non-2xx Desearch response, keeping the API's own ``detail`` text."""
    response = error.response
    detail = None
    try:
        payload = response.json()
        body_detail = payload.get("detail") if isinstance(payload, dict) else None
        if isinstance(body_detail, str):
            detail = body_detail
        elif isinstance(body_detail, list) and body_detail and isinstance(body_detail[0], dict):
            detail = body_detail[0].get("msg")
    except ValueError:
        detail = None
    reason = detail or response.reason_phrase or "request failed"
    return f"Desearch API error {response.status_code}: {reason}"
