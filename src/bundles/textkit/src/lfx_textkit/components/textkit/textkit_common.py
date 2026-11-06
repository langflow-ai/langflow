"""Shared HTTP helper for the TextKit components."""

from typing import Any

import httpx
from lfx.schema.data import Data

API_BASE_URL = "https://api.jointextkit.com/v1"
REQUEST_TIMEOUT_SECONDS = 30
DOCUMENTATION_URL = "https://jointextkit.com/docs/quickstart"


class TextKitError(Exception):
    """A TextKit request that could not be completed."""


def _error_message(response: httpx.Response) -> str:
    """Describe a non-2xx response, keeping the API's own message.

    TextKit errors carry ``{"error": {"code": ..., "message": ...}}``.
    """
    detail = None
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        detail = payload["error"].get("message") or payload["error"].get("code")
    return f"TextKit API error {response.status_code}: {detail or response.reason_phrase or 'request failed'}"


async def textkit_request(
    api_key: str | None,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call the TextKit API and return the decoded JSON object."""
    if not api_key:
        msg = "TextKit API key is required. Set the TextKit API Key input."
        raise TextKitError(msg)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "langflow-textkit-bundle",
    }
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.request(
                method, f"{API_BASE_URL}{path}", headers=headers, json=json_body, params=params
            )
    except httpx.HTTPError as e:
        msg = f"Could not reach TextKit: {e}"
        raise TextKitError(msg) from e

    if response.is_error:
        raise TextKitError(_error_message(response))
    try:
        payload = response.json()
    except ValueError as e:
        msg = "TextKit returned an unexpected response (expected JSON)."
        raise TextKitError(msg) from e
    if not isinstance(payload, dict):
        msg = "TextKit returned an unexpected response (expected a JSON object)."
        raise TextKitError(msg)
    return payload


def error_data(message: str) -> Data:
    """Return a failure as a ``Data`` row, so a flow or an Agent can read why it failed."""
    return Data(text=message, data={"error": message})
