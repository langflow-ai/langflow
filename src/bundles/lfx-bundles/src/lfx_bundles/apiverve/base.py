"""Shared HTTP plumbing for the APIVerve components.

Every request goes to the fixed host ``https://api.apiverve.com`` with the key in the
``x-api-key`` header. Redirects are not followed, so the key can never be forwarded to
another host, and the key is stripped from any text that reaches the component output.
The public API catalog is read from ``https://assets.apiverve.com`` and cached for an hour.
"""

from __future__ import annotations

import json
import re
import threading
import time
from typing import Any
from urllib.parse import quote

import httpx

API_BASE = "https://api.apiverve.com"
CATALOG_URL = "https://assets.apiverve.com/cli-manifest.json"
DOCUMENTATION_URL = "https://docs.apiverve.com"
DEFAULT_TIMEOUT_SECONDS = 60.0
CATALOG_TTL_SECONDS = 3600.0

API_KEY_INFO = (  # pragma: allowlist secret
    "APIVerve API key, sent as the x-api-key header. Get one at https://dashboard.apiverve.com."
)

_catalog: dict[str, dict[str, Any]] | None = None
_catalog_at = 0.0
_catalog_lock = threading.Lock()


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        return str(value.get_secret_value() or "").strip()
    return str(value or "").strip()


def redact(value: Any, secret: str) -> Any:
    """Replace ``secret`` everywhere inside ``value`` with ``[redacted]``."""
    if not secret:
        return value
    if isinstance(value, str):
        return value.replace(secret, "[redacted]")
    if isinstance(value, list):
        return [redact(item, secret) for item in value]
    if isinstance(value, dict):
        return {redact(k, secret): redact(v, secret) for k, v in value.items()}
    return value


def _error_message(status: int, payload: Any) -> str:
    detail = ""
    if isinstance(payload, dict):
        detail = str(payload.get("error") or payload.get("message") or "")
    if status == 401:  # noqa: PLR2004
        return "APIVerve rejected the API key."
    if status == 403:  # noqa: PLR2004
        return f"This API key is not allowed to make this call{': ' + detail if detail else '.'}"
    if status == 429:  # noqa: PLR2004
        return "Rate limit reached or monthly credits used up. Retry shortly, or upgrade at https://dashboard.apiverve.com."
    return f"APIVerve returned HTTP {status}: {detail}" if detail else f"APIVerve returned HTTP {status}."


def _query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ",".join(_query_value(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value)
    return str(value)


def clean(params: dict[str, Any] | None) -> dict[str, Any]:
    """Drop parameters that were left empty."""
    return {k: v for k, v in (params or {}).items() if v is not None and v != ""}


def call(
    api_key: str,
    path: str,
    *,
    method: str = "GET",
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """Call one APIVerve endpoint and return the ``data`` field of its response."""
    if not api_key:
        msg = "APIVerve API key is required."
        raise ValueError(msg)
    if not path.startswith("/v1/"):
        msg = "Invalid APIVerve path."
        raise ValueError(msg)
    url = API_BASE + quote(path, safe="/")
    params = {k: _query_value(v) for k, v in clean(query).items()}
    headers = {"x-api-key": api_key, "accept": "application/json"}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            if method == "POST":
                response = client.post(url, params=params, json=clean(body), headers=headers)
            else:
                response = client.get(url, params=params, headers=headers)
    except httpx.TimeoutException as exc:
        msg = f"APIVerve did not respond within {timeout:g} seconds."
        raise ValueError(msg) from exc
    except httpx.HTTPError as exc:
        msg = "APIVerve could not be reached. Retry in a moment."
        raise ValueError(msg) from exc

    try:
        payload = response.json()
    except ValueError:
        payload = None
    if not response.is_success or (isinstance(payload, dict) and payload.get("status") == "error"):
        raise ValueError(redact(_error_message(response.status_code, payload), api_key))
    if payload is None:
        msg = "APIVerve returned a non-JSON response."
        raise ValueError(msg)
    result = payload.get("data", payload) if isinstance(payload, dict) else payload
    return redact(result, api_key)


def catalog(timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, dict[str, Any]]:
    """Return ``{api_id: definition}`` from the public catalog, cached for an hour."""
    global _catalog, _catalog_at  # noqa: PLW0603 - module-level cache, guarded by _catalog_lock
    with _catalog_lock:
        if _catalog is not None and time.monotonic() - _catalog_at < CATALOG_TTL_SECONDS:
            return _catalog
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                response = client.get(CATALOG_URL, headers={"accept": "application/json"})
            response.raise_for_status()
            apis = response.json()["apis"]
            if not isinstance(apis, dict):
                msg = "Catalog 'apis' must be an object."
                raise TypeError(msg)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            if _catalog is not None:
                # Serve stale data and wait a full TTL before retrying.
                _catalog_at = time.monotonic()
                return _catalog
            msg = "The APIVerve catalog could not be loaded. Retry in a moment."
            raise ValueError(msg) from exc
        _catalog, _catalog_at = apis, time.monotonic()
        return apis


def describe(api_id: str, api: dict[str, Any]) -> dict[str, Any]:
    """Summarize one catalog entry: id, title, category, description and parameters."""
    return {
        "api": api_id,
        "title": api.get("title"),
        "category": api.get("category"),
        "description": api.get("description"),
        "parameters": [
            {
                "name": p.get("name"),
                "type": p.get("type"),
                "required": bool(p.get("required")),
                "description": p.get("description"),
                "example": p.get("example"),
            }
            for p in api.get("params", [])
        ],
    }


def search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Rank catalog APIs against a free-text query."""
    words = [w for w in (query or "").lower().split() if w]
    scored = []
    for api_id, api in catalog().items():
        title = (api.get("title") or "").lower()
        category = (api.get("category") or "").lower()
        description = (api.get("description") or "").lower()
        score = 0
        for word in words:
            # Word-start matches, so "vat" finds VAT Rates but not Gravatar.
            starts = re.compile(r"\b" + re.escape(word))
            if api_id.startswith(word) or (len(word) >= 4 and word in api_id):  # noqa: PLR2004
                score += 4
            if starts.search(title):
                score += 4
            if starts.search(category):
                score += 2
            if starts.search(description):
                score += 1
        if score or not words:
            scored.append((score, api_id, api))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [describe(api_id, api) for _, api_id, api in scored[:limit]]


def run(api_key: str, api_id: str, params: dict[str, Any], timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Any:
    """Call any catalog API by id, placing each parameter where the API expects it."""
    api_id = (api_id or "").strip().lower()
    api = catalog().get(api_id)
    if api is None:
        msg = f'Unknown APIVerve API "{api_id}". Use APIVerve Find APIs to look up the API id.'
        raise ValueError(msg)
    params = clean(params)
    declared = {p["name"]: p for p in api.get("params", [])}
    missing = [name for name, p in declared.items() if p.get("required") and name not in params]
    if missing:
        msg = f"{api_id} needs: {', '.join(missing)}."
        raise ValueError(msg)
    method = "POST" if (api.get("method") or "GET").upper() == "POST" else "GET"
    query: dict[str, Any] = {}
    body: dict[str, Any] = {}
    for name, value in params.items():
        location = declared.get(name, {}).get("in")
        if location == "query" or (location is None and method == "GET"):
            query[name] = value
        else:
            body[name] = value
    return call(
        api_key, api["path"], method=method, query=query, body=body if method == "POST" else None, timeout=timeout
    )
