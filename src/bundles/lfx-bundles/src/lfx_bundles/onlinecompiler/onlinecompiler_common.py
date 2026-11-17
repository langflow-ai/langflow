"""Shared HTTP plumbing for the OnlineCompiler.io components.

OnlineCompiler.io runs code in 46 languages, each run in a fresh sandbox with no
network, and judges it against test cases. Every component calls the fixed host
``https://api.onlinecompiler.io`` with the API key in the ``Authorization`` header.
Failures are answered as ``{"error": "..."}`` with a non-2xx status.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

API_BASE_URL = "https://api.onlinecompiler.io"
DOCUMENTATION_URL = "https://onlinecompiler.io/docs"
DEFAULT_COMPILER = "python-3.14"
# A run stops at 30 seconds on the server; the client waits a little longer.
RUN_CODE_TIMEOUT_SECONDS = 60.0
# Run Tests runs the program once per test.
RUN_TESTS_TIMEOUT_SECONDS = 120.0

API_KEY_INFO = (
    "Your OnlineCompiler.io REST API key, from the API Keys page of your dashboard. "  # pragma: allowlist secret
    "Sign up at https://onlinecompiler.io; the free plan includes 100,000 runs a month."
)
COMPILER_INFO = (
    "Compiler ID of the language, such as python-3.14, g++-15, openjdk-25 or nodejs-24. "
    "Every ID is listed at https://onlinecompiler.io/languages."
)
CHECKERS = ["trim", "exact", "tokens", "float", "rows", "table", "table_ordered"]
SCORINGS = ["percent", "all_or_nothing"]

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
_STATUS_LABELS = {
    401: "OnlineCompiler.io rejected the API key (401)",
    404: "OnlineCompiler.io did not find the API key, or it is disabled (404)",
    429: "OnlineCompiler.io plan limit reached (429)",
}


class OnlineCompilerAPIError(Exception):
    """An OnlineCompiler.io request failed; the message is safe to show in the component output."""


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def _redact(text: str, api_key: str) -> str:
    """Replace the API key in text with ***."""
    return text.replace(api_key, "***") if api_key else text


def _error_message(response: httpx.Response, api_key: str) -> str:
    """Build a short, key-free error message from a failed API response."""
    detail = ""
    try:
        body = response.json()
    except ValueError:
        detail = response.text.strip()
    else:
        if isinstance(body, dict):
            detail = str(body.get("error") or body.get("detail") or "")
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    detail = _redact(detail, api_key)[:_ERROR_DETAIL_LIMIT]
    label = _STATUS_LABELS.get(response.status_code, f"OnlineCompiler.io API error ({response.status_code})")
    return f"{label}: {detail}" if detail else label


def parse_tests(value: Any) -> list[dict[str, Any]]:
    """Turn the Tests input (a JSON array, or a list) into the API's ``tests`` list.

    Each test needs ``input`` and ``expected_output``; ``expectedOutput`` and ``output``
    are accepted for the expected output as well. ``"hidden": true`` is passed on, so the
    API returns only that test's verdict, never its output.

    Raises:
        OnlineCompilerAPIError: When the value is not a non-empty array of objects.
    """
    tests = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            tests = []
        else:
            try:
                tests = json.loads(text)
            except ValueError as exc:
                msg = 'Tests must be a JSON array, such as [{"input": "2 3", "expected_output": "5"}].'
                raise OnlineCompilerAPIError(msg) from exc
    if not isinstance(tests, list) or not tests:
        msg = 'Tests must be a non-empty JSON array, such as [{"input": "2 3", "expected_output": "5"}].'
        raise OnlineCompilerAPIError(msg)

    parsed = []
    for number, test in enumerate(tests, start=1):
        if not isinstance(test, dict):
            msg = f"Test {number} must be an object with input and expected_output."
            raise OnlineCompilerAPIError(msg)
        expected = test.get("expected_output", test.get("expectedOutput", test.get("output")))
        if expected is None:
            msg = f"Test {number} has no expected_output."
            raise OnlineCompilerAPIError(msg)
        hidden = test.get("hidden", False)
        if not isinstance(hidden, bool):
            msg = f"Test {number} hidden must be true or false."
            raise OnlineCompilerAPIError(msg)
        entry: dict[str, Any] = {"input": _as_text(test.get("input")), "expected_output": _as_text(expected)}
        if hidden:
            entry["hidden"] = True
        parsed.append(entry)
    return parsed


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return value if isinstance(value, str) else str(value)


async def onlinecompiler_post(path: str, *, api_key: Any, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    """POST a JSON payload to an OnlineCompiler.io endpoint and return the JSON answer.

    Raises:
        OnlineCompilerAPIError: On a missing key, a transport error, a non-2xx status or
            an answer that is not a JSON object.
    """
    key = secret_value(api_key)
    if not key:
        msg = "Enter an OnlineCompiler.io API key. Sign up at https://onlinecompiler.io to get one."
        raise OnlineCompilerAPIError(msg)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{API_BASE_URL}{path}",
                json=payload,
                headers={"Authorization": key, "Accept": "application/json"},
            )
    except httpx.TimeoutException as exc:
        msg = f"OnlineCompiler.io did not answer within {timeout:g} seconds."
        raise OnlineCompilerAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach the OnlineCompiler.io API: {type(exc).__name__}: {_redact(str(exc), key)}"
        raise OnlineCompilerAPIError(msg) from exc
    if not response.is_success:
        raise OnlineCompilerAPIError(_error_message(response, key))
    try:
        body = response.json()
    except ValueError as exc:
        msg = "OnlineCompiler.io returned a response that is not JSON."
        raise OnlineCompilerAPIError(msg) from exc
    if not isinstance(body, dict):
        msg = "OnlineCompiler.io returned an answer that is not a JSON object."
        raise OnlineCompilerAPIError(msg)
    return body
