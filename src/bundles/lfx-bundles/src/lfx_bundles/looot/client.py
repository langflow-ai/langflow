"""Shared HTTP helper for the looot components."""

import os
from typing import Any

import httpx

LOOOT_BASE_URL = "https://api.looot.ai"
LOOOT_TIMEOUT_SECONDS = 90.0


def default_api_key() -> str:
    """Return the looot API key from the LOOOT_TOKEN environment variable, or an empty string."""
    return os.getenv("LOOOT_TOKEN", "")


async def looot_request(
    api_key: str,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send one request to the looot REST API and return the decoded JSON body.

    Raises httpx.HTTPStatusError on a non-2xx answer, so the caller can return the error as data.
    """
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            f"{LOOOT_BASE_URL}{path}",
            headers={"Authorization": f"Bearer {api_key.strip()}"},
            params=params,
            json=json_body,
            timeout=LOOOT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()


def error_data(exc: Exception) -> dict[str, Any]:
    """Shape an exception into the error dict the components return instead of raising."""
    if isinstance(exc, httpx.HTTPStatusError):
        return {"error": f"HTTP error occurred: {exc}", "response_text": exc.response.text}
    if isinstance(exc, httpx.RequestError):
        return {"error": f"Request failed: {exc}"}
    if isinstance(exc, ValueError):
        return {"error": f"Response parsing failed: {exc}"}
    return {"error": f"An unexpected error occurred: {exc!s}"}
