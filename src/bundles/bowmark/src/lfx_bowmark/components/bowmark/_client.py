"""Shared HTTP helpers for the Bowmark components."""

import httpx

API_BASE = "https://api.bowmark.ai"
USER_AGENT = "langflow-bowmark-bundle"


def headers(api_key: str) -> dict:
    """Request headers for the Bowmark API."""
    return {
        "Authorization": f"Bearer {api_key}",
        # Identify the integration to the API; keeps traffic attributable.
        "User-Agent": USER_AGENT,
    }


def require_key(api_key: str | None) -> str:
    if not api_key:
        msg = "Bowmark API key is required. Set the Bowmark API Key input."
        raise ValueError(msg)
    return api_key


def http_error_message(error: httpx.HTTPStatusError) -> str:
    """Describe a non-2xx Bowmark response, keeping the API's own error message.

    Bowmark errors carry ``{"error": "..."}`` or ``{"error": {"message": "..."}}``.
    """
    response = error.response
    detail = None
    try:
        payload = response.json()
        body_error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(body_error, dict):
            detail = body_error.get("message") or body_error.get("code")
        elif isinstance(body_error, str):
            detail = body_error
    except ValueError:
        detail = None
    if not detail:
        body = (response.text or "").strip()
        detail = body[:300] or None
    reason = detail or response.reason_phrase or "request failed"
    return f"Bowmark API error {response.status_code}: {reason}"
