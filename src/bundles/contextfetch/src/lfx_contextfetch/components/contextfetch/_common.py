"""Shared ContextFetch API helpers for the ContextFetch components."""

import httpx
from lfx.custom.custom_component.component import Component
from lfx.schema.data import Data

API_BASE = "https://api.contextfetch.dev"
FREE_KEY_HINT = "Get a free key at https://contextfetch.dev/docs."


def http_error_message(error: httpx.HTTPStatusError) -> str:
    """Describe a non-2xx ContextFetch response, keeping the API's own error text.

    ContextFetch errors carry ``{"error": "<code>", "message": "..."}``; validation
    errors (422) carry FastAPI's ``{"detail": [{"loc": [...], "msg": "..."}]}``.
    """
    response = error.response
    detail = None
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        if isinstance(payload.get("detail"), list):
            detail = "; ".join(
                f"{'.'.join(str(p) for p in (d.get('loc') or [])[1:])}: {d.get('msg', '')}"
                for d in payload["detail"]
                if isinstance(d, dict)
            )
        else:
            detail = payload.get("message") or payload.get("error")
    reason = detail or response.reason_phrase or "request failed"
    if response.status_code == httpx.codes.UNAUTHORIZED:
        reason = f"{reason}. Check the ContextFetch API key. {FREE_KEY_HINT}"
    return f"ContextFetch API error {response.status_code}: {reason}"


def post(api_key: str, url: str, body: dict) -> dict:
    """POST a JSON body to the ContextFetch API with Bearer auth and return the decoded payload."""
    if not api_key:
        msg = f"ContextFetch API key is required. Set the ContextFetch API Key input. {FREE_KEY_HINT}"
        raise ValueError(msg)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        # Identify the integration to the API; keeps traffic attributable.
        "User-Agent": "langflow-contextfetch-bundle",
    }
    response = httpx.post(url, json=body, headers=headers, timeout=60)
    response.raise_for_status()
    return response.json()


def error_result(component: Component, message: str) -> list[Data]:
    error_data = [Data(text=message, data={"error": message})]
    component.status = error_data
    return error_data
