"""ChatLangflowLocal — validated wrapper around langchain-ollama's ChatOllama.

This wrapper backs the "Langflow Model" provider exposed in the unified model
catalog. Its only responsibility is to enforce two security guards before delegating
to ChatOllama:

  1. base_url whitelist (SSRF guard) — see ALLOWED_BASE_URLS.
  2. model name whitelist (anti-injection / unbounded download) — see CURATED_MODEL_NAMES.

Everything else — streaming, tool calling, message formatting — is inherited unchanged
from ChatOllama.
"""

from __future__ import annotations

from typing import Any

from langchain_ollama import ChatOllama

from .langflow_local_constants import (
    ALLOWED_BASE_URLS,
    CURATED_MODEL_NAMES,
    LANGFLOW_LOCAL_DEFAULT_MODEL,
)

DEFAULT_BASE_URL = "http://localhost:11434"


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


class ChatLangflowLocal(ChatOllama):
    """ChatOllama subclass restricted to the curated Langflow Model catalog."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        _ensure_langchain_ollama_available()

        chosen_url = base_url if base_url is not None else DEFAULT_BASE_URL
        chosen_model = model if model is not None else LANGFLOW_LOCAL_DEFAULT_MODEL

        _validate_base_url(chosen_url)
        _validate_model_name(chosen_model)

        super().__init__(model=chosen_model, base_url=chosen_url, **kwargs)
