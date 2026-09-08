from __future__ import annotations

from typing import Any

import httpx
from lfx.io import SecretStrInput

CONTEXT_API_BASE_URL = "https://api.context.dev/v1"
DEFAULT_TIMEOUT_SECONDS = 120


def context_api_key_input() -> SecretStrInput:
    return SecretStrInput(
        name="api_key",
        display_name="Context.dev API Key",
        info="Your Context.dev API key from https://app.context.dev/api-keys.",
        required=True,
    )


async def request_context(
    method: str,
    path: str,
    api_key: object,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token = _secret_value(api_key)
    if not token:
        msg = "Context.dev API key is required."
        raise ValueError(msg)

    try:
        async with httpx.AsyncClient(base_url=CONTEXT_API_BASE_URL, timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            response = await client.request(
                method,
                path,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                params=defined_values(params),
                json=json,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = _error_detail(exc.response)
        msg = f"Context.dev API returned HTTP {exc.response.status_code}: {detail}"
        raise ValueError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Unable to reach the Context.dev API: {exc}"
        raise ValueError(msg) from exc

    payload = response.json()
    if not isinstance(payload, dict):
        msg = "Context.dev API returned an unexpected response."
        raise TypeError(msg)
    return payload


def comma_separated_values(value: object) -> list[str] | None:
    values = [item.strip() for item in str(value or "").split(",") if item.strip()]
    return values or None


def defined_values(values: dict[str, Any] | None) -> dict[str, Any] | None:
    if values is None:
        return None
    return {key: value for key, value in values.items() if value is not None and value != ""}


def _secret_value(value: object) -> str:
    get_secret_value = getattr(value, "get_secret_value", None)
    if callable(get_secret_value):
        return str(get_secret_value()).strip()
    return str(value or "").strip()


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or response.reason_phrase

    if isinstance(payload, dict):
        for key in ("error_description", "message", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return response.reason_phrase
