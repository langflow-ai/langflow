"""Shared HTTP plumbing for the TestMu AI components.

TestMu AI (formerly LambdaTest) is a cloud testing platform. Both components call
the Automation API on the fixed host ``https://api.lambdatest.com`` with HTTP Basic
authentication: the TestMu AI username and access key.
"""

from __future__ import annotations

from typing import Any

import httpx

API_BASE_URL = "https://api.lambdatest.com"
DOCUMENTATION_URL = "https://www.testmuai.com/support/api-doc/"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_LIMIT = 100

USERNAME_INFO = "Your TestMu AI username, shown on the account security page."
ACCESS_KEY_INFO = "Your TestMu AI access key, shown next to your username on the account security page."

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
_STATUS_LABELS = {
    401: "TestMu AI rejected the username or access key (401)",
    429: "TestMu AI rate limit exceeded (429)",
}


class TestMuAIAPIError(Exception):
    """A TestMu AI request failed; the message is safe to show in the component output."""

    __test__ = False  # the name starts with "Test"; keep pytest from collecting it


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def clamp_limit(value: Any) -> int:
    """Clamp a requested row count to 1..MAX_LIMIT."""
    try:
        limit = int(value or 1)
    except (TypeError, ValueError):
        limit = 1
    return min(max(limit, 1), MAX_LIMIT)


def _redact(text: str, access_key: str) -> str:
    return text.replace(access_key, "***") if access_key else text


def _error_message(response: httpx.Response, access_key: str) -> str:
    detail = ""
    try:
        body = response.json()
    except ValueError:
        detail = response.text.strip()
    else:
        if isinstance(body, dict):
            detail = str(body.get("message") or body.get("error") or "")
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    detail = _redact(detail, access_key)[:_ERROR_DETAIL_LIMIT]
    label = _STATUS_LABELS.get(response.status_code, f"TestMu AI API error ({response.status_code})")
    return f"{label}: {detail}" if detail else label


def fetch_rows(
    path: str,
    *,
    username: Any,
    access_key: Any,
    timeout: float,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """GET an Automation API list endpoint and return its ``data`` rows.

    Raises:
        TestMuAIAPIError: On missing credentials, a transport error, a non-2xx status,
            or a body without a ``data`` list.
    """
    user = secret_value(username)
    key = secret_value(access_key)
    if not user or not key:
        msg = "Enter your TestMu AI username and access key."
        raise TestMuAIAPIError(msg)
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request("GET", f"{API_BASE_URL}{path}", params=params, auth=(user, key))
    except httpx.TimeoutException as exc:
        msg = f"TestMu AI request timed out after {timeout:g} seconds."
        raise TestMuAIAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach the TestMu AI API: {type(exc).__name__}: {_redact(str(exc), key)}"
        raise TestMuAIAPIError(msg) from exc
    if not response.is_success:
        raise TestMuAIAPIError(_error_message(response, key))
    try:
        body = response.json()
    except ValueError as exc:
        msg = "TestMu AI API returned a response that is not JSON."
        raise TestMuAIAPIError(msg) from exc
    rows = body.get("data") if isinstance(body, dict) else None
    if rows is None:
        return []
    if not isinstance(rows, list):
        msg = "TestMu AI API returned an unexpected response shape."
        raise TestMuAIAPIError(msg)
    return [row for row in rows if isinstance(row, dict)]
