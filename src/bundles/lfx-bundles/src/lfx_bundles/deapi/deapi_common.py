"""Shared HTTP plumbing for the deAPI components.

deAPI runs open-source image, video and audio models behind one REST API at the
fixed host ``https://api.deapi.ai``. Every generation call submits a job and
returns a ``request_id``; the components poll ``GET /api/v2/jobs/{request_id}``
until the job is done. Each model publishes its own defaults and limits in
``GET /api/v2/models``, so the components read those instead of hard-coding sizes.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

API_BASE_URL = "https://api.deapi.ai/api/v2"
DOCUMENTATION_URL = "https://docs.deapi.ai"
API_KEY_INFO = "Your deAPI API key. Create one at https://app.deapi.ai."
REQUEST_TIMEOUT_SECONDS = 60.0
POLL_INTERVAL_SECONDS = 4.0
# A job keeps running (and billing) on deAPI even if one status poll fails, so a few
# consecutive transient poll errors are retried before giving up.
MAX_POLL_ERRORS = 3

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
_STATUS_LABELS = {
    401: "deAPI rejected the API key (401)",
    402: "deAPI account balance is too low (402)",
    422: "deAPI rejected the request (422)",
    429: "deAPI rate limit exceeded (429)",
}


class DeapiAPIError(Exception):
    """A deAPI request failed; the message is safe to show in the component output."""


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def _redact(text: str, api_key: str) -> str:
    return text.replace(api_key, "***") if api_key else text


def _error_message(response: httpx.Response, api_key: str) -> str:
    detail = ""
    try:
        body = response.json()
    except ValueError:
        detail = response.text.strip()
    else:
        if isinstance(body, dict):
            detail = str(body.get("message") or body.get("error") or "")
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    detail = _redact(detail, api_key)[:_ERROR_DETAIL_LIMIT]
    label = _STATUS_LABELS.get(response.status_code, f"deAPI error ({response.status_code})")
    return f"{label}: {detail}" if detail else label


def deapi_request(
    method: str,
    path: str,
    *,
    api_key: Any,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Call the deAPI REST API and return the JSON body.

    Raises:
        DeapiAPIError: When the key is missing, on a transport error, a non-2xx status,
            or a body that is not a JSON object.
    """
    key = secret_value(api_key)
    if not key:
        msg = "Enter a deAPI API key. Create one at https://app.deapi.ai."
        raise DeapiAPIError(msg)
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request(method, f"{API_BASE_URL}{path}", params=params, json=json, headers=headers)
    except httpx.TimeoutException as exc:
        msg = f"deAPI request timed out after {timeout:g} seconds."
        raise DeapiAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach the deAPI API: {type(exc).__name__}: {_redact(str(exc), key)}"
        raise DeapiAPIError(msg) from exc
    if not response.is_success:
        raise DeapiAPIError(_error_message(response, key))
    try:
        body = response.json()
    except ValueError as exc:
        msg = "deAPI returned a response that is not JSON."
        raise DeapiAPIError(msg) from exc
    if not isinstance(body, dict):
        msg = "deAPI returned an unexpected response shape."
        raise DeapiAPIError(msg)
    return body


def list_models(api_key: Any, inference_type: str) -> list[dict[str, Any]]:
    """Return the models available to the account for one inference type, such as ``txt2img``."""
    models: list[dict[str, Any]] = []
    page, last_page = 1, 1
    while page <= last_page:
        body = deapi_request("GET", "/models", api_key=api_key, params={"per_page": 100, "page": page})
        models.extend(item for item in body.get("data") or [] if isinstance(item, dict))
        meta = body.get("meta")
        last_page = meta.get("last_page", 1) if isinstance(meta, dict) else 1
        page += 1
    return [model for model in models if inference_type in (model.get("inference_types") or [])]


def model_slugs(api_key: Any, inference_type: str, fallback: list[str]) -> list[str]:
    """Return model slugs for a dropdown, or ``fallback`` when the catalog cannot be read."""
    try:
        slugs = [str(model["slug"]) for model in list_models(api_key, inference_type) if model.get("slug")]
    except DeapiAPIError:
        return fallback
    return slugs or fallback


def find_model(api_key: Any, inference_type: str, slug: str) -> dict[str, Any]:
    """Return one model from the catalog.

    Raises:
        DeapiAPIError: When the model is not available to the account for this inference type.
    """
    for model in list_models(api_key, inference_type):
        if model.get("slug") == slug:
            return model
    msg = f"The model {slug!r} is not available to this deAPI account for {inference_type}."
    raise DeapiAPIError(msg)


def model_info(model: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the model's ``(defaults, limits)``; either is empty when the catalog omits it."""
    info = model.get("info") if isinstance(model.get("info"), dict) else {}
    defaults = info.get("defaults") if isinstance(info.get("defaults"), dict) else {}
    limits = info.get("limits") if isinstance(info.get("limits"), dict) else {}
    return defaults, limits


def pick_int(value: Any, default: Any, minimum: Any = None, maximum: Any = None) -> int | None:
    """Use ``value`` when it is a positive integer, else ``default``, clamped to the model's limits."""
    try:
        chosen = int(value) if value not in (None, "") and int(value) > 0 else None
    except (TypeError, ValueError):
        chosen = None
    if chosen is None:
        try:
            chosen = int(default) if default not in (None, "") else None
        except (TypeError, ValueError):
            chosen = None
    if chosen is None:
        return None
    if isinstance(minimum, int | float):
        chosen = max(chosen, int(minimum))
    if isinstance(maximum, int | float):
        chosen = min(chosen, int(maximum))
    return chosen


def run_job(path: str, payload: dict[str, Any], *, api_key: Any, max_wait_seconds: float) -> dict[str, Any]:
    """Submit a job, poll it until it finishes, and return the job.

    The returned job has ``request_id``, ``status`` and, when done, ``result_url`` and/or
    ``result``. If the job is still running after ``max_wait_seconds``, it is returned with
    its current ``status`` so the caller can report the ``request_id``.

    Raises:
        DeapiAPIError: When the submission is rejected or the job fails.
    """
    body = deapi_request("POST", path, api_key=api_key, json=payload)
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    request_id = data.get("request_id")
    if not request_id:
        msg = "deAPI accepted the request but returned no request_id."
        raise DeapiAPIError(msg)

    deadline = time.monotonic() + max(float(max_wait_seconds), 0.0)
    poll_errors = 0
    while True:
        try:
            status_body = deapi_request("GET", f"/jobs/{request_id}", api_key=api_key)
        except DeapiAPIError as exc:
            poll_errors += 1
            if poll_errors >= MAX_POLL_ERRORS or time.monotonic() + POLL_INTERVAL_SECONDS > deadline:
                msg = f"Could not read the status of deAPI job {request_id}: {exc}"
                raise DeapiAPIError(msg) from exc
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        poll_errors = 0
        job = status_body.get("data") if isinstance(status_body.get("data"), dict) else {}
        # ``preview`` is a large in-progress base64 thumbnail, not useful as output.
        job = {key: value for key, value in job.items() if key != "preview"}
        job["request_id"] = request_id
        status = job.get("status")
        if status == "done":
            return job
        if status == "error":
            reason = job.get("error_reason") or job.get("error_code") or "unknown error"
            refunded = " The charge was refunded." if job.get("refunded") else ""
            msg = f"deAPI job {request_id} failed: {reason}.{refunded}"
            raise DeapiAPIError(msg)
        if time.monotonic() + POLL_INTERVAL_SECONDS > deadline:
            return job
        time.sleep(POLL_INTERVAL_SECONDS)


def error_payload(message: str) -> dict[str, Any]:
    """Return an error in the shape every deAPI component output uses for failures."""
    return {"text": message, "error": message}


def job_payload(job: dict[str, Any], *, kind: str, url_key: str | None = None) -> dict[str, Any]:
    """Shape a finished (or still running) job into the ``Data`` payload a component returns.

    ``text`` is the output text: the result URL when ``url_key`` is given (the URL is also
    stored under that key, for example ``image_url``), otherwise the inline ``result``.
    """
    request_id = job.get("request_id")
    if job.get("status") != "done":
        message = (
            f"The deAPI {kind} job {request_id} is still {job.get('status')} after Max Wait. "
            f"It keeps running; read its result from {API_BASE_URL}/jobs/{request_id}."
        )
        return {**error_payload(message), "request_id": request_id, "status": job.get("status")}
    payload: dict[str, Any] = {"request_id": request_id, "status": "done"}
    if job.get("result_url"):
        payload["result_url"] = job["result_url"]
    if url_key:
        if not job.get("result_url"):
            return error_payload(f"deAPI finished the {kind} job {request_id} but returned no result URL.")
        return {**payload, url_key: job["result_url"], "text": job["result_url"]}
    if job.get("result") is None:
        return error_payload(f"deAPI finished the {kind} job {request_id} but returned no result.")
    return {**payload, "text": str(job["result"])}
