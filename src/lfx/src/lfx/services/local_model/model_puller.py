"""Async checks and downloads of curated Ollama models.

External-client layer over the Ollama HTTP API:
  - GET  /api/tags  → list installed models
  - POST /api/pull  → start a streaming pull (NDJSON)

Two security guards (same as ChatLangflowLocal in Slice 1):
  - base_url MUST be in ALLOWED_BASE_URLS                     (SSRF guard)
  - model_name MUST be in CURATED_MODEL_NAMES                  (DoS / unbounded download)

Success of pull_model is decided ONLY by the terminator chunk `{"status":"success"}`.
Partial progress chunks are forwarded to the caller via progress_callback but
never count as success.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from lfx.base.models.langflow_local_constants import ALLOWED_BASE_URLS, CURATED_MODEL_NAMES
from lfx.base.models.langflow_local_model import UncuratedModelError, UnsafeBaseUrlError

_TAGS_TIMEOUT_S = 5.0
_PULL_TOTAL_TIMEOUT_S = 1800.0  # 30 min hard cap on a single pull
_HTTP_OK = 200

ProgressCallback = Callable[[dict[str, Any]], None]


class PullStatus(str, Enum):
    SUCCESS = "success"
    ALREADY_PRESENT = "already_present"
    FAILED = "failed"
    NETWORK_ERROR = "network_error"
    REJECTED = "rejected"


@dataclass(frozen=True)
class PullOutcome:
    status: PullStatus
    message: str = ""


def _validate_base_url(base_url: str) -> None:
    if base_url not in ALLOWED_BASE_URLS:
        msg = "base_url is not in the Langflow Model allowlist"
        raise UnsafeBaseUrlError(msg)


def _validate_model_name(model_name: str) -> None:
    if model_name not in CURATED_MODEL_NAMES:
        msg = "model is not in the Langflow Model curated set"
        raise UncuratedModelError(msg)


async def is_model_pulled(model_name: str, base_url: str, timeout_s: float = _TAGS_TIMEOUT_S) -> bool:
    """Return True iff `model_name` appears in Ollama's /api/tags listing."""
    _validate_base_url(base_url)
    _validate_model_name(model_name)
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.get(f"{base_url}/api/tags")
    except httpx.HTTPError:
        return False
    if response.status_code != _HTTP_OK:
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    if not isinstance(payload, dict):
        return False
    models = payload.get("models", [])
    if not isinstance(models, list):
        return False
    return any(isinstance(m, dict) and m.get("name") == model_name for m in models)


async def pull_model(
    model_name: str,
    base_url: str,
    progress_callback: ProgressCallback,
    timeout_s: float = _PULL_TOTAL_TIMEOUT_S,
) -> PullOutcome:
    """Pull `model_name` from Ollama, forwarding NDJSON chunks to the callback."""
    _validate_base_url(base_url)
    _validate_model_name(model_name)

    if await is_model_pulled(model_name, base_url):
        return PullOutcome(status=PullStatus.ALREADY_PRESENT, message=f"{model_name} is already pulled")

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            return await _consume_pull_stream(client, model_name, base_url, progress_callback)
    except httpx.HTTPError as exc:
        return PullOutcome(status=PullStatus.NETWORK_ERROR, message=f"{exc.__class__.__name__}")


async def _consume_pull_stream(
    client: httpx.AsyncClient,
    model_name: str,
    base_url: str,
    progress_callback: ProgressCallback,
) -> PullOutcome:
    saw_success = False
    async with client.stream("POST", f"{base_url}/api/pull", json={"name": model_name}) as response:
        async for raw in response.aiter_lines():
            if not raw:
                continue
            try:
                chunk = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(chunk, dict):
                continue
            if "error" in chunk:
                return PullOutcome(status=PullStatus.FAILED, message=str(chunk["error"]))
            progress_callback(chunk)
            if chunk.get("status") == "success":
                saw_success = True

    if saw_success:
        return PullOutcome(status=PullStatus.SUCCESS, message=f"{model_name} pulled")
    return PullOutcome(status=PullStatus.FAILED, message="stream ended without success terminator")
