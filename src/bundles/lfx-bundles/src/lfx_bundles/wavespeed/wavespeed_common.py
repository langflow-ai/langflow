"""Shared HTTP plumbing for the WaveSpeed components.

WaveSpeed runs image and video models behind one REST API. A run is submitted with
``POST /api/v3/<model id>`` and its result is read from
``GET /api/v3/predictions/<id>/result`` until it reaches a final status. Every
answer is wrapped as ``{"code": 200, "message": "success", "data": {...}}``; a
``code`` other than 200 is a failure even when the HTTP status is 200.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import urlsplit

import httpx

API_BASE_URL = "https://api.wavespeed.ai/api/v3"
DOCUMENTATION_URL = "https://wavespeed.ai/docs"
API_KEY_INFO = "Your WaveSpeed API key. Create one at https://wavespeed.ai/accesskey."  # pragma: allowlist secret

# Each HTTP call is limited by REQUEST_TIMEOUT_SECONDS; the whole run, submission included, by the
# component's own timeout.
REQUEST_TIMEOUT_SECONDS = 60.0
POLL_INTERVAL_SECONDS = 2.0
# Backoff for transient poll answers (429, 5xx, network errors): doubles from POLL_INTERVAL_SECONDS up to
# this cap, or follows Retry-After when the API sends it.
MAX_BACKOFF_SECONDS = 30.0
# Model ids are slash-separated path segments such as ``bytedance/seedream-v5.5/edit``.
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)+$")
_PREDICTION_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_FAILED_STATUSES = {"failed", "cancelled", "canceled", "timeout", "deleted"}
# Poll answers worth retrying: the prediction keeps running while the API recovers.
_TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_ERROR_DETAIL_LIMIT = 300


class WaveSpeedAPIError(Exception):
    """A WaveSpeed request failed; the message is safe to show in the component output.

    ``prediction_id`` is set once the run was accepted, so the caller can keep it and read the
    result later instead of submitting (and paying for) the run again.
    """

    def __init__(self, message: str, prediction_id: str | None = None) -> None:
        super().__init__(message)
        self.prediction_id = prediction_id


def result_url(prediction_id: str) -> str:
    """URL that returns the run's status and outputs (needs the API key)."""
    return f"{API_BASE_URL}/predictions/{prediction_id}/result"


def error_data(exc: WaveSpeedAPIError) -> dict[str, Any]:
    """The ``data`` of a failed component run: the message, plus the run's id when it was accepted."""
    data: dict[str, Any] = {"error": str(exc)}
    if exc.prediction_id:
        data["prediction_id"] = exc.prediction_id
        data["result_url"] = result_url(exc.prediction_id)
    return data


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def clean_model_id(value: Any, default: str) -> str:
    """Return the model id without surrounding whitespace or slashes, or raise when it is malformed."""
    model_id = str(value or "").strip().strip("/") or default
    if not _MODEL_ID.match(model_id):
        msg = f"Enter a WaveSpeed model id such as {default}; got {model_id!r}."
        raise WaveSpeedAPIError(msg)
    return model_id


def http_url(value: Any, label: str) -> str:
    """Return a stripped absolute http(s) URL, or raise with a message naming the field."""
    url = str(value or "").strip()
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
    except ValueError:  # e.g. an unmatched bracket in the host
        valid = False
    if not valid:
        msg = f"{label} must be an absolute http(s) URL; got {url!r}."
        raise WaveSpeedAPIError(msg)
    return url


def parse_extra_input(value: Any) -> dict[str, Any]:
    """Parse the optional JSON object of extra model inputs (empty when unset)."""
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        extra = json.loads(text)
    except ValueError as exc:
        msg = f"Extra Input must be a JSON object: {exc}"
        raise WaveSpeedAPIError(msg) from exc
    if not isinstance(extra, dict):
        msg = 'Extra Input must be a JSON object, such as {"seed": 42}.'
        raise WaveSpeedAPIError(msg)
    return extra


def _redact(text: str, api_key: str) -> str:
    """Replace the API key in text with ***."""
    return text.replace(api_key, "***") if api_key else text


def _error_message(response: httpx.Response, api_key: str) -> str:
    """Build a short, key-free error message from a failed HTTP response."""
    try:
        body = response.json()
    except ValueError:
        detail = response.text.strip()
    else:
        detail = str(body.get("message") or "") if isinstance(body, dict) else ""
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    detail = _redact(detail, api_key)[:_ERROR_DETAIL_LIMIT]
    label = f"WaveSpeed API error ({response.status_code})"
    return f"{label}: {detail}" if detail else label


def _envelope_data(response: httpx.Response, api_key: str) -> dict[str, Any]:
    """Return the ``data`` object of a successful answer, or raise on any kind of failure."""
    if not response.is_success:
        raise WaveSpeedAPIError(_error_message(response, api_key))
    try:
        body = response.json()
    except ValueError as exc:
        msg = "WaveSpeed API returned a response that is not JSON."
        raise WaveSpeedAPIError(msg) from exc
    if not isinstance(body, dict):
        msg = "WaveSpeed API returned an unexpected response (expected a JSON object)."
        raise WaveSpeedAPIError(msg)
    code = body.get("code")
    if code is not None and code != 200:  # noqa: PLR2004
        detail = _redact(str(body.get("message") or ""), api_key)[:_ERROR_DETAIL_LIMIT]
        msg = f"WaveSpeed API error ({code}): {detail}" if detail else f"WaveSpeed API error ({code})"
        raise WaveSpeedAPIError(msg)
    data = body.get("data")
    if not isinstance(data, dict):
        msg = "WaveSpeed API returned an answer without a data object."
        raise WaveSpeedAPIError(msg)
    return data


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


_UNKNOWN_SUBMIT = (
    "The run may still have been accepted and billed; check your WaveSpeed history "
    "(https://wavespeed.ai/history) before running the component again."
)


async def _submit(
    client: httpx.AsyncClient, model_id: str, payload: dict[str, Any], key: str, request_timeout: float
) -> str:
    """Submit one run and return its prediction id.

    Never retried: every accepted submission is a new, billed run. When the outcome is unknown (a timeout,
    a connection lost after sending, or a 5xx answer), the error says so instead of submitting again.
    """
    try:
        response = await client.post(
            f"{API_BASE_URL}/{model_id}", json=payload, headers=_headers(key), timeout=request_timeout
        )
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        # The request never reached the API, so no run was created.
        msg = f"Could not reach the WaveSpeed API: {type(exc).__name__}: {_redact(str(exc), key)}"
        raise WaveSpeedAPIError(msg) from exc
    except httpx.TimeoutException as exc:
        msg = f"WaveSpeed did not answer the submission in time. {_UNKNOWN_SUBMIT}"
        raise WaveSpeedAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"The connection to WaveSpeed failed during the submission ({type(exc).__name__}). {_UNKNOWN_SUBMIT}"
        raise WaveSpeedAPIError(msg) from exc
    if response.status_code >= 500:  # noqa: PLR2004
        msg = f"{_error_message(response, key)}. {_UNKNOWN_SUBMIT}"
        raise WaveSpeedAPIError(msg)
    data = _envelope_data(response, key)
    prediction_id = str(data.get("id") or "")
    if not _PREDICTION_ID.match(prediction_id):
        msg = "WaveSpeed accepted the run but returned no usable prediction id."
        raise WaveSpeedAPIError(msg)
    return prediction_id


def _retry_after(response: httpx.Response | None) -> float | None:
    """Seconds from a numeric Retry-After header, if any."""
    if response is None:
        return None
    try:
        return max(0.0, float(response.headers.get("Retry-After", "")))
    except ValueError:
        return None


async def _poll(client: httpx.AsyncClient, prediction_id: str, key: str) -> list[str]:
    """Poll the result until the run reaches a final status; return its output URLs.

    Reading the result is safe to repeat, so 408, 429, 5xx and network errors are retried with
    exponential backoff (or Retry-After); the caller's deadline bounds the whole loop.
    """
    url = result_url(prediction_id)
    delay = POLL_INTERVAL_SECONDS
    while True:
        await asyncio.sleep(delay)
        try:
            response = await client.get(url, headers=_headers(key))
        except httpx.RequestError:
            response = None
        if response is None or response.status_code in _TRANSIENT_STATUS_CODES:
            backoff = min(max(delay, POLL_INTERVAL_SECONDS) * 2, MAX_BACKOFF_SECONDS)
            hint = _retry_after(response)
            delay = min(hint, MAX_BACKOFF_SECONDS) if hint is not None else backoff
            continue
        delay = POLL_INTERVAL_SECONDS
        data = _envelope_data(response, key)
        status = str(data.get("status") or "").lower()
        if status == "completed":
            raw_outputs = data.get("outputs")
            if not isinstance(raw_outputs, list):
                msg = f"WaveSpeed run {prediction_id} completed, but its outputs are not a list."
                raise WaveSpeedAPIError(msg)
            outputs = [item for item in raw_outputs if isinstance(item, str) and item]
            if not outputs:
                msg = f"WaveSpeed run {prediction_id} completed without any output."
                raise WaveSpeedAPIError(msg)
            return outputs
        if status in _FAILED_STATUSES:
            detail = _redact(str(data.get("error") or ""), key)[:_ERROR_DETAIL_LIMIT]
            msg = f"WaveSpeed run {prediction_id} {status}" + (f": {detail}" if detail else ".")
            raise WaveSpeedAPIError(msg)


async def run_prediction(
    model_id: str,
    payload: dict[str, Any],
    *,
    api_key: Any,
    timeout: float,
) -> tuple[str, list[str]]:
    """Run one WaveSpeed model and return ``(prediction id, output URLs)``.

    The run is submitted once and its result polled every ``POLL_INTERVAL_SECONDS``
    until it completes, fails, or ``timeout`` seconds pass (submission included). Errors raised
    after the run was accepted carry its ``prediction_id``.

    Raises:
        WaveSpeedAPIError: On a missing key, a transport error, a non-2xx status or
            non-200 ``code``, a failed, cancelled or timed-out run, or a run still
            going after ``timeout`` seconds.
    """
    key = secret_value(api_key)
    if not key:
        msg = "Enter a WaveSpeed API key. Create one at https://wavespeed.ai/accesskey."
        raise WaveSpeedAPIError(msg)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout  # covers the submission and the polling
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        submit_timeout = max(0.001, min(REQUEST_TIMEOUT_SECONDS, deadline - loop.time()))
        prediction_id = await _submit(client, model_id, payload, key, submit_timeout)
        # HTTPX timeouts limit each network operation, so polling also needs an overall deadline.
        try:
            outputs = await asyncio.wait_for(
                _poll(client, prediction_id, key), timeout=max(0.0, deadline - loop.time())
            )
        except asyncio.TimeoutError as exc:
            msg = (
                f"WaveSpeed run {prediction_id} did not finish within {timeout:g} seconds. It may still finish: "
                f"read its result at {result_url(prediction_id)} instead of running the component again."
            )
            raise WaveSpeedAPIError(msg, prediction_id) from exc
        except WaveSpeedAPIError as exc:
            exc.prediction_id = exc.prediction_id or prediction_id
            raise
    return prediction_id, outputs
