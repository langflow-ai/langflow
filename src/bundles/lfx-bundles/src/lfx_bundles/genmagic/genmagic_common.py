"""Shared HTTP plumbing for the GenMagic components.

GenMagic (https://genmagic.co) is one API key and one pay-as-you-go balance for hundreds of
image, video, audio and text models behind an OpenAI-compatible REST API
(https://genmagic.co/openapi.json). Every component calls the fixed host
``https://genmagic.co`` over HTTPS with ``Authorization: Bearer <key>`` and names Langflow in the
``X-GenMagic-Client`` header. The host is not an input, so there is no tenant-controlled endpoint
that could receive the key.

Generations are billed to the key's balance when they succeed, and each response reports the cost
in the ``X-Cost-Cents`` header and the remaining balance in ``X-Credits-Remaining``. The public
model catalog (``GET /api/v1/models``) needs no key, so the model dropdowns also load before a key
is set.
"""

from __future__ import annotations

import time
from functools import cache
from importlib import metadata
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable

API_BASE_URL = "https://genmagic.co"
API_PREFIX = "/api/v1"
DOCUMENTATION_URL = "https://genmagic.co/developers"
API_KEYS_URL = "https://genmagic.co/get-api-key"
PRICING_URL = "https://genmagic.co/pricing"
VERIFY_EMAIL_URL = "https://genmagic.co/verify-email"

API_KEY_VARIABLE = "GENMAGIC_API_KEY"  # pragma: allowlist secret
API_KEY_INFO = f"Your GenMagic API key. Create one at {API_KEYS_URL}. Generations are billed to the key's balance."

# The model dropdown value that lets GenMagic pick its recommended model (the request omits ``model``).
AUTO_MODEL = "auto"

DEFAULT_TIMEOUT_SECONDS = 180.0
CATALOG_TIMEOUT_SECONDS = 15.0
VIDEO_REQUEST_TIMEOUT_SECONDS = 60.0

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
# Consecutive failed polls tolerated while a (paid) video job is rendering.
MAX_POLL_FAILURES = 5
VIDEO_DONE_STATES = frozenset({"completed", "failed"})


class GenMagicAPIError(ValueError):
    """A GenMagic request failed. The message is safe to show in the component status."""

    def __init__(self, message: str, *, status: int = 0, code: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.code = code

    @property
    def transient(self) -> bool:
        """Whether the same request may succeed if repeated (network error, rate limit, server error)."""
        return self.status in {0, 429} or self.status >= 500  # noqa: PLR2004


class GenMagicVideoTimeoutError(GenMagicAPIError):
    """A video job was still rendering when the wait ran out. ``job`` is its last known state."""

    def __init__(self, message: str, *, job: dict[str, Any], costs: dict[str, float]) -> None:
        super().__init__(message, code="timeout")
        self.job = job
        self.costs = costs


@cache
def client_header() -> str:
    """The ``X-GenMagic-Client`` value: ``langflow/<version>`` so GenMagic can tell Langflow usage apart."""
    for distribution in ("langflow", "lfx"):
        try:
            return f"langflow/{metadata.version(distribution)}"
        except metadata.PackageNotFoundError:
            continue
    return "langflow/unknown"


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def text_value(value: Any) -> str:
    """A stripped string from a text input, which may be a ``Message`` when wired from another component."""
    text = getattr(value, "text", value)
    return str(text or "").strip()


def optional_positive_int(value: Any) -> int | None:
    """``value`` as a positive integer, or ``None`` when it is empty, zero or not a number."""
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def positive_seconds(value: Any, default: float) -> float:
    """``value`` as a positive number of seconds, falling back to ``default``."""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return default
    return seconds if seconds > 0 else default


def chosen_model(value: Any) -> str | None:
    """The model id to send, or ``None`` (omit the field) for empty or ``auto``."""
    model = text_value(value)
    return None if not model or model.casefold() == AUTO_MODEL else model


def _redact(text: str, api_key: str) -> str:
    return text.replace(api_key, "***") if api_key else text


def _error_fields(response: httpx.Response) -> tuple[str, str]:
    """The ``code`` and ``message`` of GenMagic's OpenAI-style ``{"error": {...}}`` body (or the raw text)."""
    try:
        body = response.json()
    except ValueError:
        body = None
    code = message = ""
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            code = str(error.get("code") or "")
            message = str(error.get("message") or "")
        elif isinstance(error, str):
            message = error
    return code, message or " ".join(response.text.split())


def _api_error(response: httpx.Response, api_key: str) -> GenMagicAPIError:
    status = response.status_code
    code, detail = _error_fields(response)
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    detail = _redact(detail, api_key)[:_ERROR_DETAIL_LIMIT]
    hint = ""
    if code == "email_verification_required":
        headline = "The email address of your GenMagic account is not verified"
        hint = f"Verify it at {VERIFY_EMAIL_URL}, then try again"
    elif status == httpx.codes.UNAUTHORIZED:
        headline, detail = "GenMagic rejected the API key (401)", ""
        hint = f"Create a key at {API_KEYS_URL}"
    elif status == httpx.codes.PAYMENT_REQUIRED:
        headline = "Your GenMagic balance is too low for this request (402)"
        hint = f"Add credits at {PRICING_URL}"
    elif status == httpx.codes.TOO_MANY_REQUESTS:
        headline = "GenMagic rate limit reached (429)"
        hint = "Wait a moment and try again"
    else:
        headline = f"GenMagic API error ({status}{', ' + code if code else ''})"
    message = f"{headline}: {detail}" if detail else headline
    if hint:
        message = f"{message}. {hint}"
    return GenMagicAPIError(message, status=status, code=code)


def _send(
    method: str,
    path: str,
    *,
    api_key: str,
    timeout: float,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    headers = {"Accept": "application/json, audio/*", "X-GenMagic-Client": client_header()}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = f"{API_BASE_URL}{API_PREFIX}{path}"
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.request(method, url, params=params, json=json, headers=headers)
    except httpx.TimeoutException as exc:
        msg = f"GenMagic did not answer within {timeout:g} seconds."
        raise GenMagicAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach GenMagic: {type(exc).__name__}: {_redact(str(exc), api_key)}"
        raise GenMagicAPIError(msg) from exc
    if not response.is_success:
        raise _api_error(response, api_key)
    return response


def require_api_key(value: Any) -> str:
    """The stripped API key, or a ``GenMagicAPIError`` that says where to get one."""
    api_key = secret_value(value)
    if not api_key:
        msg = f"A GenMagic API key is required. Create one at {API_KEYS_URL}."
        raise GenMagicAPIError(msg, status=401, code="missing_api_key")
    return api_key


def call_api(
    method: str,
    path: str,
    *,
    api_key: Any,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    json: dict[str, Any] | None = None,
) -> httpx.Response:
    """Send an authenticated request to ``/api/v1<path>`` and return the successful response.

    Raises:
        GenMagicAPIError: When the key is missing, the request fails, or GenMagic answers with an error.
    """
    key = require_api_key(api_key)
    return _send(method, path, api_key=key, timeout=timeout, json=json)


def response_json(response: httpx.Response) -> dict[str, Any]:
    """The JSON object in ``response``."""
    try:
        body = response.json()
    except ValueError as exc:
        msg = "GenMagic returned a response that is not JSON."
        raise GenMagicAPIError(msg, status=response.status_code) from exc
    if not isinstance(body, dict):
        msg = "GenMagic returned an unexpected response shape."
        raise GenMagicAPIError(msg, status=response.status_code)
    return body


def metering(response: httpx.Response) -> dict[str, float]:
    """What the call cost and what is left, in US cents, from the response headers."""
    fields = {"cost_cents": "X-Cost-Cents", "balance_cents": "X-Credits-Remaining"}
    values: dict[str, float] = {}
    for key, header in fields.items():
        raw = response.headers.get(header)
        try:
            if raw is not None:
                values[key] = float(raw)
        except ValueError:
            continue
    return values


# --------------------------------------------------------------------------- model catalog


def list_models(category: str) -> list[dict[str, Any]]:
    """The public catalog for one category (``image``, ``video``, ``audio`` or ``text``), newest first.

    Reading the catalog needs no API key and spends no credits.
    """
    response = _send("GET", "/models", api_key="", timeout=CATALOG_TIMEOUT_SECONDS, params={"category": category})
    data = response_json(response).get("data")
    models = [m for m in (data if isinstance(data, list) else []) if isinstance(m, dict) and m.get("id")]

    def newest_first(model: dict[str, Any]) -> tuple[int, str]:
        created = optional_positive_int(model.get("created")) or 0
        return -created, str(model.get("name") or model["id"]).casefold()

    return sorted(models, key=newest_first)


def refresh_model_dropdown(
    build_config: dict,
    field_name: str,
    category: str,
    *,
    include_auto: bool,
    keep: Callable[[dict[str, Any]], bool] | None = None,
) -> dict:
    """Fill the ``field_name`` dropdown from the live catalog; leave it as it was when GenMagic is unreachable."""
    try:
        models = list_models(category)
    except GenMagicAPIError:
        models = []
    ids = [str(m["id"]) for m in models if keep is None or keep(m)]
    options = [AUTO_MODEL, *ids] if include_auto else ids
    if options:
        build_config[field_name]["options"] = options
    return build_config


# --------------------------------------------------------------------------- video jobs


def video_path(job_id: str) -> str:
    return f"/videos/{quote(job_id, safe='')}"


def video_result(job: dict[str, Any], extra: dict[str, float] | None = None) -> dict[str, Any]:
    """The fields of a video job worth returning: id, model, status, hosted ``url``, ``error`` and cost."""
    result = {key: job[key] for key in ("id", "model", "status", "url", "error", "cost_cents") if job.get(key)}
    for key, value in (extra or {}).items():
        result.setdefault(key, value)
    return result


def wait_for_video(
    job: dict[str, Any],
    *,
    api_key: Any,
    timeout: float,
    poll_interval: float,
    sleep: Callable[[float], None] | None = None,
    clock: Callable[[], float] | None = None,
) -> tuple[dict[str, Any], dict[str, float]]:
    """Poll ``job`` until it is ``completed`` or ``failed``, for at most ``timeout`` seconds.

    A video is billed once, when it completes, and the render continues on GenMagic's side after this
    function gives up, so a timeout (``GenMagicVideoTimeoutError``) names the job ID for
    ``GenMagic Video Status`` to pick up later.
    A few failed polls (network error, rate limit, server error) are tolerated; an error that retrying
    cannot fix (bad key, empty balance, unknown job) is raised at once.

    Returns:
        The last job body and the cost headers of the last successful poll.

    Raises:
        GenMagicAPIError: On a poll error that is not transient, too many failed polls, or the timeout.
    """
    job_id = str(job.get("id") or "")
    if not job_id:
        msg = "GenMagic did not return a video job ID."
        raise GenMagicAPIError(msg)
    pause = sleep or time.sleep
    now = clock or time.monotonic
    deadline = now() + timeout
    costs: dict[str, float] = {}
    failures = 0
    while job.get("status") not in VIDEO_DONE_STATES:
        remaining = deadline - now()
        if remaining <= 0:
            msg = (
                f"Video job {job_id} is still {job.get('status') or 'processing'} after {timeout:g} seconds. "
                "It keeps rendering and is billed only when it completes: fetch it later with the "
                "GenMagic Video Status component, or raise the timeout."
            )
            raise GenMagicVideoTimeoutError(msg, job=job, costs=costs)
        pause(min(poll_interval, remaining))
        try:
            response = call_api("GET", video_path(job_id), api_key=api_key, timeout=VIDEO_REQUEST_TIMEOUT_SECONDS)
            job = response_json(response)
        except GenMagicAPIError as exc:
            failures += 1
            if not exc.transient or failures >= MAX_POLL_FAILURES:
                msg = f"{exc} (video job {job_id}; fetch it later with the GenMagic Video Status component)"
                raise GenMagicAPIError(msg, status=exc.status, code=exc.code) from exc
            continue
        failures = 0
        costs = metering(response)
    return job, costs
