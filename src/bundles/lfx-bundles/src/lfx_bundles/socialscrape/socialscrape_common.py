"""Shared HTTP plumbing for the SocialScrape components.

SocialScrape is a social media data API. Every component calls the fixed host
``https://api.socialscrape.dev`` with the API key in the ``x-api-key`` header.
Successful answers are wrapped as ``{"ok": true, "data": {...}, ...}``; failures
as ``{"ok": false, "error": {"code", "message", "retryable"}, ...}``.
"""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

API_BASE_URL = "https://api.socialscrape.dev"
DOCUMENTATION_URL = "https://socialscrape.dev/docs"
DEFAULT_TIMEOUT_SECONDS = 60.0
# How long a queued job is polled before the component gives up, and how often.
JOB_WAIT_SECONDS = 90.0
JOB_POLL_SECONDS = 3.0
_JOB_ID = re.compile(r"^job_[A-Za-z0-9]+$")

API_KEY_INFO = "Your SocialScrape API key. Sign up at https://socialscrape.dev/sign-up to get one."

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
_STATUS_LABELS = {
    401: "SocialScrape rejected the API key (401)",
    402: "SocialScrape account is out of credits (402)",
    429: "SocialScrape rate limit exceeded (429)",
}


class SocialScrapeAPIError(Exception):
    """A SocialScrape request failed; the message is safe to show in the component output."""


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def bare_handle(value: Any) -> str:
    """Return the handle without surrounding whitespace or a leading ``@``, or raise when it is empty."""
    handle = str(value or "").strip().removeprefix("@").strip()
    if not handle:
        msg = "Enter a profile handle, such as nasa."
        raise SocialScrapeAPIError(msg)
    return handle


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
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            detail = str(error.get("message") or error.get("code") or "")
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    detail = _redact(detail, api_key)[:_ERROR_DETAIL_LIMIT]
    label = _STATUS_LABELS.get(response.status_code, f"SocialScrape API error ({response.status_code})")
    return f"{label}: {detail}" if detail else label


def _get_data(path: str, *, key: str, timeout: float, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET one SocialScrape path and return the ``data`` object of the answer."""
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                f"{API_BASE_URL}{path}",
                params=params or {},
                headers={"x-api-key": key, "accept": "application/json"},
            )
    except httpx.TimeoutException as exc:
        msg = f"SocialScrape request timed out after {timeout:g} seconds."
        raise SocialScrapeAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach the SocialScrape API: {type(exc).__name__}: {_redact(str(exc), key)}"
        raise SocialScrapeAPIError(msg) from exc
    if not response.is_success:
        raise SocialScrapeAPIError(_error_message(response, key))
    try:
        body = response.json()
    except ValueError as exc:
        msg = "SocialScrape API returned a response that is not JSON."
        raise SocialScrapeAPIError(msg) from exc
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        msg = "SocialScrape API returned an answer without a data object."
        raise SocialScrapeAPIError(msg)
    return data


def socialscrape_request(
    path: str,
    *,
    api_key: Any,
    timeout: float,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """GET a SocialScrape endpoint and return the ``data`` object of the finished answer.

    Empty parameters are left out of the query string. A request still running
    after about 25 seconds is answered with a job on any endpoint; that job is
    polled, for free, until it finishes or ``JOB_WAIT_SECONDS`` pass, so a job is
    never returned as if it were the result.

    Raises:
        SocialScrapeAPIError: On a missing key, a transport error, a non-2xx status,
            an answer without a ``data`` object, or a job still running after the wait.
    """
    key = secret_value(api_key)
    if not key:
        msg = "Enter a SocialScrape API key. Sign up at https://socialscrape.dev/sign-up to get one."
        raise SocialScrapeAPIError(msg)
    query = {name: value for name, value in (params or {}).items() if value not in (None, "")}
    data = _get_data(path, key=key, timeout=timeout, params=query)
    if data.get("object") != "job":
        return data

    job_id = str(data.get("job_id") or "")
    if not _JOB_ID.match(job_id):
        msg = "SocialScrape queued a job without a usable job id."
        raise SocialScrapeAPIError(msg)
    deadline = time.monotonic() + JOB_WAIT_SECONDS
    while time.monotonic() < deadline:
        time.sleep(JOB_POLL_SECONDS)
        data = _get_data(f"/v1/jobs/{job_id}", key=key, timeout=timeout)
        if data.get("object") != "job":
            return data
    msg = f"SocialScrape is still working on this request (job {job_id}). Try again in a minute."
    raise SocialScrapeAPIError(msg)
