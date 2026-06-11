"""Shared Resemble Detect + Intelligence client for the Langflow components.

No Langflow dependency, so it can be exercised directly by the test harness.
Mirrors the live-verified contract: Bearer auth, `{success, item}` envelopes,
async poll-to-completion, `Prefer: wait` for watermark.
"""

from __future__ import annotations

import time
from typing import Any

import requests

DEFAULT_BASE_URL = "https://app.resemble.ai/api/v2"
TERMINAL = {"completed", "failed", "error", "cancelled", "success"}
HTTP_BAD_REQUEST = 400


def request(
    api_key: str,
    base_url: str | None,
    method: str,
    path: str,
    body: dict | None = None,
    extra_headers: dict | None = None,
    timeout: int = 60,
) -> Any:
    if not api_key:
        msg = "Missing Resemble API key."
        raise ValueError(msg)
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    url = (base_url or DEFAULT_BASE_URL).strip().rstrip("/") + "/" + path.lstrip("/")
    resp = requests.request(method, url, json=body, headers=headers, timeout=(10, timeout))
    if resp.status_code in (401, 403):
        msg = "Resemble authentication failed — check your API key."
        raise ValueError(msg)
    try:
        data = resp.json()
    except ValueError:
        data = {"raw": resp.text}
    if resp.status_code >= HTTP_BAD_REQUEST:
        detail = (data or {}).get("message") if isinstance(data, dict) else None
        msg = f"Resemble API error on {method} {path}: {detail or resp.status_code}"
        raise ValueError(msg)
    return data


def item(data: Any) -> dict:
    if isinstance(data, dict) and isinstance(data.get("item"), dict):
        return data["item"]
    return data if isinstance(data, dict) else {}


def poll(api_key: str, base_url: str | None, path: str, max_wait: int = 120) -> Any:
    wait = max(1, int(max_wait or 120))
    deadline = time.monotonic() + wait
    delay = 2
    last = request(api_key, base_url, "GET", path)
    while True:
        status = item(last).get("status")
        if not status or str(status).lower() in TERMINAL:
            return last
        if time.monotonic() >= deadline:
            msg = f"Timed out after {wait}s waiting for {path} to complete (last status: {status})."
            raise ValueError(msg)
        time.sleep(delay)
        delay = min(10, delay + 1)
        last = request(api_key, base_url, "GET", path)


def sanitize(data: Any, n: int = 200) -> Any:
    if isinstance(data, dict):
        return {k: sanitize(v, n) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize(v, n) for v in data]
    if isinstance(data, str) and data.startswith("data:") and len(data) > n:
        return f"<inline base64 omitted — {len(data)} chars>"
    return data
