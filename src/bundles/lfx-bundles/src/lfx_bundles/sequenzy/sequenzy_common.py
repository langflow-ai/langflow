"""Shared HTTP plumbing for the Sequenzy components.

Sequenzy is an email marketing platform for SaaS and ecommerce. Every component
calls the public REST API at the fixed host ``https://api.sequenzy.com`` and
authenticates with a Sequenzy API key sent as a Bearer token.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from lfx.io import FloatInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

API_BASE_URL = "https://api.sequenzy.com/api/v1"
DOCUMENTATION_URL = "https://docs.sequenzy.com"
DEFAULT_TIMEOUT_SECONDS = 30.0

API_KEY_INFO = "Your Sequenzy API key. Create one in the Sequenzy dashboard."

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
_STATUS_LABELS = {
    401: "Sequenzy rejected the API key (401)",
    403: "The Sequenzy API key lacks the scope for this action (403)",
    404: "Sequenzy could not find the requested resource (404)",
    429: "Sequenzy rate limit exceeded (429)",
}


def api_key_input() -> SecretStrInput:
    return SecretStrInput(
        name="api_key",
        display_name="Sequenzy API Key",
        info=API_KEY_INFO,
        required=True,
    )


def timeout_input() -> FloatInput:
    return FloatInput(
        name="timeout",
        display_name="Timeout (seconds)",
        info="How long to wait for Sequenzy to answer.",
        value=DEFAULT_TIMEOUT_SECONDS,
        advanced=True,
    )


class SequenzyAPIError(Exception):
    """A Sequenzy request failed; the message is safe to show in the component output."""


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def text_value(value: Any) -> str:
    """Return a component input as a stripped string (empty when unset)."""
    return str(value or "").strip()


def parse_json_object(value: Any, field_name: str) -> dict[str, Any]:
    """Read a JSON object from a dict input or JSON text; an empty value is an empty object.

    Raises:
        SequenzyAPIError: When the text is not a JSON object.
    """
    if isinstance(value, dict):
        return value
    if hasattr(value, "data") and isinstance(value.data, dict):
        return value.data
    text = text_value(value)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except ValueError as exc:
        msg = f'{field_name} must be a JSON object, such as {{"plan": "pro"}}.'
        raise SequenzyAPIError(msg) from exc
    if not isinstance(parsed, dict):
        msg = f'{field_name} must be a JSON object, such as {{"plan": "pro"}}.'
        raise SequenzyAPIError(msg)
    return parsed


def parse_list(value: Any) -> list[str]:
    """Split comma-separated text, or a list, into non-empty stripped strings."""
    items = value if isinstance(value, list) else str(value or "").split(",")
    return [str(item).strip() for item in items if str(item).strip()]


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
            detail = str(body.get("error") or body.get("message") or "")
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    detail = _redact(detail, api_key)[:_ERROR_DETAIL_LIMIT]
    label = _STATUS_LABELS.get(response.status_code, f"Sequenzy API error ({response.status_code})")
    return f"{label}: {detail}" if detail else label


def sequenzy_request(
    method: str,
    path: str,
    *,
    api_key: Any,
    timeout: float,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Call a Sequenzy API endpoint and return the JSON body.

    Raises:
        SequenzyAPIError: On a missing key, a transport error, a non-2xx status,
            or a body that is not a JSON object.
    """
    key = secret_value(api_key)
    if not key:
        msg = "Enter a Sequenzy API key."
        raise SequenzyAPIError(msg)
    headers = {**(extra_headers or {}), "Authorization": f"Bearer {key}", "Accept": "application/json"}
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request(method, f"{API_BASE_URL}{path}", params=params, json=json_body, headers=headers)
    except httpx.TimeoutException as exc:
        msg = f"Sequenzy request timed out after {timeout:g} seconds."
        raise SequenzyAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach the Sequenzy API: {type(exc).__name__}: {_redact(str(exc), key)}"
        raise SequenzyAPIError(msg) from exc
    if not response.is_success:
        raise SequenzyAPIError(_error_message(response, key))
    try:
        body = response.json()
    except ValueError as exc:
        msg = "Sequenzy API returned a response that is not JSON."
        raise SequenzyAPIError(msg) from exc
    if not isinstance(body, dict):
        msg = "Sequenzy API returned an unexpected response shape."
        raise SequenzyAPIError(msg)
    return body


def error_data(component: Any, error: str) -> Data:
    """Log an error, show it as the component status and return it as ``Data``."""
    logger.error(error)
    component.status = error
    return Data(text=error, data={"error": error})


def call_sequenzy(component: Any, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    """``sequenzy_request`` with the component's API key and timeout."""
    return sequenzy_request(
        method,
        path,
        api_key=component.api_key,
        timeout=float(component.timeout or DEFAULT_TIMEOUT_SECONDS),
        **kwargs,
    )
