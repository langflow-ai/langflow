"""Shared helpers for the GenMagic component tests: every request is intercepted at ``httpx.Client.request``."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx_bundles.genmagic.genmagic_common import API_BASE_URL, API_PREFIX

# Placeholder credential for the mocked API (not a real key).
API_KEY = "gm_live_test-placeholder-key"  # pragma: allowlist secret


def api_url(path: str) -> str:
    return f"{API_BASE_URL}{API_PREFIX}{path}"


def response(
    status_code: int = 200,
    *,
    json_body: Any = None,
    text: str | None = None,
    content: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request("GET", API_BASE_URL)
    if content is not None:
        return httpx.Response(status_code, content=content, headers=headers, request=request)
    if text is not None:
        return httpx.Response(status_code, text=text, headers=headers, request=request)
    return httpx.Response(status_code, json=json_body, headers=headers, request=request)


@pytest.fixture
def no_sleep():
    """Polling waits are skipped; the patched ``time.sleep`` is returned so a test can count the waits."""
    with patch("time.sleep") as sleep:
        yield sleep
