"""Shared request helper for the Geekflare API components."""

from __future__ import annotations

from typing import Any

import httpx

API_BASE_URL = "https://api.geekflare.com"
DEFAULT_TIMEOUT = 180.0


class GeekflareAPIError(Exception):
    """The Geekflare API returned an error or couldn't be reached."""


def normalize_url(url: str | None) -> str:
    """Accept bare domains such as ``example.com`` by adding ``https://``."""
    url = (url or "").strip()
    if url and "://" not in url:
        url = f"https://{url}"
    return url


def call_api(api_key: str | None, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST a JSON body to a Geekflare endpoint and return the decoded response.

    ``None`` and empty-string values are dropped so the API applies its defaults.
    Raises ``GeekflareAPIError`` with the API's own message on any failure.
    """
    if not api_key:
        msg = "Geekflare API key is required. Set the Geekflare API Key input."
        raise GeekflareAPIError(msg)

    body = {k: v for k, v in payload.items() if v is not None and v != ""}
    headers = {
        "x-api-key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "langflow-geekflare-bundle",
    }
    try:
        response = httpx.post(f"{API_BASE_URL}/{path}", json=body, headers=headers, timeout=DEFAULT_TIMEOUT)
    except httpx.HTTPError as e:
        msg = f"Request to Geekflare failed: {e}"
        raise GeekflareAPIError(msg) from e

    try:
        data: Any = response.json()
    except ValueError:
        data = {"message": response.text}
    if not isinstance(data, dict):
        data = {"data": data}

    if response.status_code >= httpx.codes.BAD_REQUEST or data.get("apiStatus") == "failure":
        reason = data.get("message") or response.reason_phrase or "request failed"
        msg = f"Geekflare API error {response.status_code}: {reason}"
        raise GeekflareAPIError(msg)
    return data
