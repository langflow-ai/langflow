"""Single-submit HTTP client and conservative task result normalization."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

API_BASE = "https://api.acedata.cloud"
_FAILED = {"failed", "error", "cancelled", "canceled", "rejected"}
_DONE = {"complete", "completed", "succeeded", "succeed", "success", "finished"}
_MEDIA_KEYS = {
    "image_url",
    "audio_url",
    "video_url",
    "file_url",
    "raw_image_url",
    "url",
}
_PRIVATE_KEYS = {
    "request",
    "request_body",
    "user_id",
    "actor_user_id",
    "credential_id",
    "authorization_id",
    "application_id",
    "api_key",
    "access_token",
    "refresh_token",
    "authorization",
    "headers",
    "supplier",
    "supplier_id",
    "provider_route",
    "upstream",
    "upstream_model",
    "actual_model",
    "secret",
}


class AceAPIError(RuntimeError):
    """Public error that never includes credentials or a raw service payload."""


async def post_json(
    path: str,
    key: str,
    body: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, Any] | list[Any]:
    """Make one HTTP request. Generation is never retried automatically."""
    if not key or not key.strip():
        msg = "Enter an Ace Data Cloud application API key."
        raise AceAPIError(msg)
    if not path.startswith("/") or ".." in path:
        msg = "Invalid Ace Data Cloud route."
        raise ValueError(msg)
    request_headers = {"Authorization": f"Bearer {key.strip()}"}
    if headers:
        request_headers.update(headers)
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=45, follow_redirects=False) as client:
            response = await client.post(path, json=body, headers=request_headers)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        msg = f"Ace Data Cloud HTTP {status}. Check access, balance, and request history before another submission."
        raise AceAPIError(msg) from None
    except (httpx.RequestError, json.JSONDecodeError):
        msg = "Ace Data Cloud response was unavailable. Check request history before submitting again."
        raise AceAPIError(msg) from None
    if not isinstance(payload, (dict, list)):
        msg = "Ace Data Cloud returned an unexpected response. Check request history."
        raise AceAPIError(msg)
    return payload


def scrub(value: Any) -> Any:
    """Return customer-safe result data without credential or route metadata."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key.lower() in _PRIVATE_KEYS or re.search(
                r"(^internal(?:_|$)|supplier|upstream|(?:^|_)secret(?:_|$))",
                key,
                re.IGNORECASE,
            ):
                continue
            if key.lower() == "error" and item:
                result[key] = {"message": "Task failed; inspect its task or trace ID in request history."}
            else:
                result[key] = scrub(item)
        return result
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


def media_urls(value: Any) -> list[str]:
    urls: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                if key in _MEDIA_KEYS and isinstance(item, str) and item.startswith("https://"):
                    urls.append(item)
                elif isinstance(item, (dict, list)):
                    walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    return list(dict.fromkeys(urls))


def _task_id(body: Any) -> str:
    if not isinstance(body, dict):
        return ""
    nested = body.get("task")
    value = body.get("task_id") or (nested.get("id") if isinstance(nested, dict) else None)
    return str(value or "")


def normalize(
    body: dict[str, Any] | list[Any],
    *,
    service: str,
    retrieved: bool = False,
    requested_task_id: str = "",
) -> dict[str, Any]:
    """Only report success after a terminal task or a synchronous result."""
    task_id = requested_task_id or _task_id(body)
    response: Any = body.get("response", body) if retrieved and isinstance(body, dict) else body
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except json.JSONDecodeError:
            response = {}
    safe = scrub(response)
    states: list[str] = []
    has_error = False

    def visit(node: Any) -> None:
        nonlocal has_error
        if isinstance(node, dict):
            if node.get("success") is False or node.get("error"):
                has_error = True
            for key, item in node.items():
                if key in {"state", "status"} and isinstance(item, str):
                    states.append(item.lower())
                elif key in {"data", "content", "task"}:
                    visit(item)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(response)
    if retrieved and isinstance(body, dict):
        visit({k: v for k, v in body.items() if k != "response"})
    unfinished = retrieved and isinstance(body, dict) and "finished_at" in body and body["finished_at"] is None
    failed = has_error or any(state in _FAILED for state in states)
    urls = media_urls(safe)
    completed_by_state = bool(states) and all(state in _DONE for state in states)
    completed_by_record = bool(retrieved and isinstance(body, dict) and body.get("finished_at") and response)
    completed_by_url = bool(retrieved and urls and not states)
    if unfinished:
        status = "pending"
    elif failed:
        status = "failed"
    elif completed_by_state or completed_by_record or completed_by_url:
        status = "succeeded"
    elif task_id:
        status = "pending"
    elif response:
        status = "succeeded"
    else:
        msg = "No task ID or completed result was returned. Check request history before submitting again."
        raise AceAPIError(msg)
    trace_id = body.get("trace_id", "") if isinstance(body, dict) else ""
    return {
        "service": service,
        "status": status,
        "success": status == "succeeded",
        "task_id": task_id,
        "trace_id": str(trace_id or ""),
        "media_urls": urls if status == "succeeded" else [],
        "result": safe,
    }
