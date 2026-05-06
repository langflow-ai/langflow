"""Async HTTP probes against an Ollama server — health and version.

External-client layer: only HTTP, no business logic. Every public function:
  - validates base_url against the same allowlist as ChatLangflowLocal (SSRF guard)
  - enforces an explicit timeout (never relies on httpx defaults)
  - coerces network failures into bool/None — callers never see exceptions on the
    network path. Programmer errors (bad URL, bad arg) still raise.
"""

from __future__ import annotations

import httpx

from lfx.base.models.langflow_local_constants import ALLOWED_BASE_URLS
from lfx.base.models.langflow_local_model import UnsafeBaseUrlError

_DEFAULT_TIMEOUT_S = 2.0
_HTTP_OK = 200


def _validate_base_url(base_url: str) -> None:
    if base_url not in ALLOWED_BASE_URLS:
        msg = "base_url is not in the Langflow Model allowlist"
        raise UnsafeBaseUrlError(msg)


async def is_ollama_running(base_url: str, timeout_s: float = _DEFAULT_TIMEOUT_S) -> bool:
    """Return True iff Ollama responds with HTTP 200 to GET /api/version."""
    _validate_base_url(base_url)
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.get(f"{base_url}/api/version")
    except httpx.HTTPError:
        return False
    return response.status_code == _HTTP_OK


async def ollama_version(base_url: str, timeout_s: float = _DEFAULT_TIMEOUT_S) -> str | None:
    """Return the Ollama server version string, or None if unreachable / malformed."""
    _validate_base_url(base_url)
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.get(f"{base_url}/api/version")
    except httpx.HTTPError:
        return None
    if response.status_code != _HTTP_OK:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    version = payload.get("version") if isinstance(payload, dict) else None
    return version if isinstance(version, str) else None
