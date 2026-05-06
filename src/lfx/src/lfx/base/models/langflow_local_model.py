"""ChatLangflowLocal — validated wrapper around langchain-ollama's ChatOllama.

This wrapper backs the "Langflow Model" provider exposed in the unified model
catalog. Responsibilities, in order:

  1. SSRF guard — see ALLOWED_BASE_URLS.
  2. Anti-injection guard — see CURATED_MODEL_NAMES.
  3. Auto-pull on demand — if the curated model is not pulled yet on the bundled
     Ollama backend, fetch it synchronously before delegating to ChatOllama.

Everything else — streaming, tool calling, message formatting — is inherited unchanged
from ChatOllama.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from langchain_ollama import ChatOllama

from .langflow_local_constants import (
    ALLOWED_BASE_URLS,
    CURATED_MODEL_NAMES,
    LANGFLOW_LOCAL_DEFAULT_MODEL,
)

DEFAULT_BASE_URL = "http://localhost:11434"

_TAGS_TIMEOUT_S = 5.0
_PULL_TIMEOUT_S = 1800.0  # 30 min hard cap


class UnsafeBaseUrlError(ValueError):
    """Raised when base_url falls outside the whitelist (SSRF guard)."""


class UncuratedModelError(ValueError):
    """Raised when model name is not in the curated, allowed set."""


class LangchainOllamaMissingError(ImportError):
    """Raised when langchain-ollama is unavailable at runtime."""


def _ensure_langchain_ollama_available() -> None:
    # Why a runtime re-check (vs. relying on the module-level import above):
    # the package may be uninstalled or unloaded between class load and instantiation
    # (e.g. by tests that patch sys.modules to simulate the missing-dep scenario).
    # Surfacing a clear, actionable error here is much friendlier than letting an
    # AttributeError or NoneType failure surface deep inside pydantic.
    try:
        import langchain_ollama  # noqa: F401
    except ImportError as exc:
        msg = "langchain-ollama is required. Please install it: uv pip install langchain-ollama"
        raise LangchainOllamaMissingError(msg) from exc


def _validate_base_url(base_url: str) -> None:
    if base_url not in ALLOWED_BASE_URLS:
        # Why a fixed message (no input echoed back): the unsafe value can carry
        # CRLF or shell metacharacters; echoing it into a log/exception message
        # enables log injection. Operators can still inspect the raw value via
        # the upstream caller's request log if needed.
        msg = "base_url is not in the Langflow Model allowlist"
        raise UnsafeBaseUrlError(msg)


def _validate_model_name(model: str) -> None:
    if model not in CURATED_MODEL_NAMES:
        msg = "model is not in the Langflow Model curated set"
        raise UncuratedModelError(msg)


def _is_model_pulled_sync(model: str, base_url: str) -> bool:
    """Synchronous variant of services.local_model.model_puller.is_model_pulled.

    Why duplicate (vs. importing the async version): __init__ runs in sync code paths
    (component.build_model is synchronous). Using asyncio.run() here would either
    crash inside an existing event loop or deadlock when called from one.
    """
    try:
        with httpx.Client(timeout=_TAGS_TIMEOUT_S) as client:
            response = client.get(f"{base_url}/api/tags")
    except httpx.HTTPError:
        return False
    if response.status_code != 200:  # noqa: PLR2004
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    if not isinstance(payload, dict):
        return False
    models = payload.get("models", [])
    return isinstance(models, list) and any(
        isinstance(m, dict) and m.get("name") == model for m in models
    )


def _pull_model_sync(model: str, base_url: str) -> None:
    """Synchronous Ollama pull. Streams NDJSON; raises on error or stream-without-success."""
    saw_success = False
    with httpx.Client(timeout=_PULL_TIMEOUT_S) as client, client.stream(
        "POST", f"{base_url}/api/pull", json={"name": model}
    ) as response:
        response.raise_for_status()
        for raw in response.iter_lines():
            if not raw:
                continue
            try:
                chunk = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(chunk, dict):
                continue
            if "error" in chunk:
                msg = f"Ollama pull error: {chunk['error']}"
                raise RuntimeError(msg)
            if chunk.get("status") == "success":
                saw_success = True
    if not saw_success:
        msg = "Ollama pull stream ended without a success terminator"
        raise RuntimeError(msg)


def _ensure_model_available(model: str, base_url: str) -> None:
    """No-op if model is already pulled; otherwise pulls it synchronously.

    Failures are swallowed silently — the subsequent ChatOllama call will surface
    the original 404 error to the user, which is the existing UX. We just give it
    a chance to succeed instead of guaranteeing it.
    """
    try:
        if _is_model_pulled_sync(model, base_url):
            return
        _pull_model_sync(model, base_url)
    except (httpx.HTTPError, RuntimeError):
        # If pull fails, fall through — let the actual invoke surface its own error.
        return


class ChatLangflowLocal(ChatOllama):
    """ChatOllama subclass restricted to the curated Langflow Model catalog."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        *,
        auto_pull: bool = True,
        **kwargs: Any,
    ) -> None:
        _ensure_langchain_ollama_available()

        chosen_url = base_url if base_url is not None else DEFAULT_BASE_URL
        chosen_model = model if model is not None else LANGFLOW_LOCAL_DEFAULT_MODEL

        _validate_base_url(chosen_url)
        _validate_model_name(chosen_model)

        if auto_pull:
            _ensure_model_available(chosen_model, chosen_url)

        super().__init__(model=chosen_model, base_url=chosen_url, **kwargs)
