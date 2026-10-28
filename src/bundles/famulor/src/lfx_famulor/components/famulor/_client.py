"""HTTP helpers for the public Famulor REST API v1.

The host is fixed at ``https://app.famulor.io``. Callers never supply a URL,
so these helpers do not accept a user-controlled base address.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID

import httpx
from lfx.inputs.inputs import SecretStrInput
from lfx.schema.data import Data
from lfx.schema.message import Message

API_ROOT = "https://app.famulor.io/api/v1"
USER_AGENT = "langflow-famulor-bundle"
REQUEST_TIMEOUT_SECONDS = 30
MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50
MAX_VARIABLE_LENGTH = 2000
_E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def api_key_input() -> SecretStrInput:
    """Shared secret input. The key stays on the component and is not a tool argument."""
    return SecretStrInput(
        name="famulor_api_key",
        display_name="Famulor API Key",
        required=True,
        password=True,
        info=(
            "Workspace API key (fam_...). Create one under Settings, API & MCP. "
            "See https://docs.famulor.io/api-reference/introduction."
        ),
    )


def http_error_message(error: httpx.HTTPStatusError) -> str:
    """Describe a non-2xx Famulor response, keeping the API's own error message.

    Public API errors use ``{"error": {"code": ..., "message": ...}}``.
    """
    response = error.response
    detail = None
    code = None
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        body_error = payload.get("error")
        if isinstance(body_error, dict):
            message = body_error.get("message")
            error_code = body_error.get("code")
            detail = message if isinstance(message, str) and message.strip() else None
            code = error_code if isinstance(error_code, str) and error_code.strip() else None
        elif isinstance(payload.get("message"), str) and payload["message"].strip():
            detail = payload["message"].strip()
    reason = detail or response.reason_phrase or "request failed"
    if code:
        return f"Famulor API error {response.status_code} ({code}): {reason}"
    return f"Famulor API error {response.status_code}: {reason}"


def error_data(message: str) -> Data:
    """One-row failure result. The text is also the message output."""
    return Data(text=message, data={"error": message})


def error_message(result: Data) -> Message:
    """Chat-facing view of a Data result, including an error row."""
    text = result.text or ""
    failed = isinstance(result.data, dict) and "error" in result.data
    return Message(text=text, error=failed)


def require_api_key(api_key: str | None) -> str:
    """Return a stripped key or raise when the secret input is empty."""
    key = (api_key or "").strip()
    if not key:
        msg = "Famulor API key is required. Set the Famulor API Key input."
        raise ValueError(msg)
    return key


def require_uuid(value: str | None, label: str) -> str:
    """Validate a required UUID and keep the caller's spelling."""
    text = (value or "").strip()
    if not text:
        msg = f"{label} is required."
        raise ValueError(msg)
    try:
        UUID(text)
    except ValueError as exc:
        msg = f"{label} must be a UUID."
        raise ValueError(msg) from exc
    return text


def optional_uuid(value: str | None, label: str) -> str | None:
    """Validate an optional UUID. Blank means the field is omitted."""
    text = (value or "").strip()
    if not text:
        return None
    return require_uuid(text, label)


def require_e164(value: str | None) -> str:
    """Validate a destination phone number in E.164 format."""
    text = (value or "").strip()
    if not _E164.fullmatch(text):
        msg = "Phone number must be E.164, for example +4930123456."
        raise ValueError(msg)
    return text


def normalize_variables(value: Any) -> dict[str, str | int | float | bool]:
    """Accept a dict or a JSON object of strings, numbers, and booleans.

    The API rejects nested values and limits each string to 2000 characters.
    """
    if value is None or value in ("", {}):
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            msg = "Variables must be a JSON object."
            raise ValueError(msg) from exc
    if not isinstance(value, Mapping):
        msg = "Variables must be a JSON object."
        raise TypeError(msg)
    cleaned: dict[str, str | int | float | bool] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            msg = "Variable names must be non-empty strings."
            raise ValueError(msg)
        if isinstance(item, bool | int | float):
            cleaned[key] = item
            continue
        if isinstance(item, str):
            if len(item) > MAX_VARIABLE_LENGTH:
                msg = f"Variable {key!r} exceeds {MAX_VARIABLE_LENGTH} characters."
                raise ValueError(msg)
            cleaned[key] = item
            continue
        msg = f"Variable {key!r} must be a string, number, or boolean."
        raise ValueError(msg)
    return cleaned


def clamp_page(limit: int | None, offset: int | None) -> tuple[int, int]:
    """Clamp list pagination to the API bounds (limit 1-200, offset >= 0)."""
    requested = DEFAULT_PAGE_SIZE if limit is None else int(limit)
    bounded_limit = max(1, min(requested, MAX_PAGE_SIZE))
    requested_offset = 0 if offset is None else int(offset)
    return bounded_limit, max(0, requested_offset)


def request_json(
    method: str,
    path: str,
    api_key: str | None,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call one public Famulor API path and return the decoded JSON object."""
    key = require_api_key(api_key)
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    response = httpx.request(
        method,
        f"{API_ROOT}{path}",
        headers=headers,
        params=params,
        json=json_body,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        msg = "Famulor API returned an unexpected response (expected JSON)."
        raise ValueError(msg) from exc
    if not isinstance(payload, dict):
        msg = "Famulor API returned an unexpected response (expected a JSON object)."
        raise TypeError(msg)
    return payload


def unwrap_data(payload: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """Return ``data`` plus ``meta`` from a successful envelope."""
    if "data" not in payload:
        msg = "Famulor API returned an unexpected response (missing data)."
        raise ValueError(msg)
    meta = payload.get("meta")
    return payload["data"], meta if isinstance(meta, dict) else {}


def page_total(meta: dict[str, Any], fallback: int) -> int:
    """Read ``meta.pagination.total`` when the API sent it."""
    pagination = meta.get("pagination")
    if isinstance(pagination, dict) and isinstance(pagination.get("total"), int):
        return pagination["total"]
    return fallback


def transcript_text(transcript: Any) -> str:
    """Flatten a call transcript into ``role: text`` lines.

    The public call payload may be ``null``, an ``items`` object, or a list of
    ``{role, content}`` turns. Tool-call entries without spoken text are skipped.
    """
    if not transcript:
        return ""
    items = transcript.get("items") if isinstance(transcript, dict) else transcript
    if not isinstance(items, list):
        return ""
    lines: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        content = _content_text(item.get("content", item.get("text")))
        if not content:
            continue
        role = item.get("role") or item.get("sender") or "message"
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [_content_text(part) if not isinstance(part, dict) else _dict_text(part) for part in content]
        return " ".join(part for part in parts if part).strip()
    if isinstance(content, dict):
        return _dict_text(content)
    return ""


def _dict_text(part: dict[str, Any]) -> str:
    for key in ("text", "transcript", "content"):
        value = part.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def call_text(call: dict[str, Any]) -> str:
    """Short readable view of one call: status, failure, summary, transcript."""
    call_id = call.get("id") or ""
    status = call.get("status") or "unknown"
    lines = [f"Call {call_id} is {status}."]
    failure = call.get("failure")
    if isinstance(failure, dict):
        failure_message = failure.get("message")
        if isinstance(failure_message, str) and failure_message.strip():
            lines.append(failure_message.strip())
    summary = call.get("summary")
    if isinstance(summary, str) and summary.strip():
        lines.append(summary.strip())
    spoken = transcript_text(call.get("transcript"))
    if spoken:
        lines.append(spoken)
    return "\n".join(lines)


def guard(callback):
    """Turn transport, HTTP, and validation errors into a single error Data row."""
    try:
        return callback()
    except httpx.HTTPStatusError as exc:
        return error_data(http_error_message(exc))
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return error_data(str(exc))
