"""Leak-safe LLM-provider latency and error metrics ("is it us or them").

Records outbound LLM-provider health as METRICS, never spans, keyed only on provider, model and
error type. No URLs, no prompts, no completions, no error message strings ever reach a label, so
provider API keys that ride in request URLs cannot leak the way they did through the httpx span
path (removed from the export allowlist in :mod:`lfx.observability`).

The instruments are created from the allowlisted "langflow" meter, so they export through the
same application-only filter as the rest of the runtime's own metrics. ``metrics.get_meter``
returns a no-op meter when no provider is installed, so this is safe under ``lfx serve``.

OpenTelemetry is an optional lfx extra (``lfx[otel]``). When it is absent there is no meter to
record on, so :func:`get_llm_provider_metrics_handler` returns None and the callback is simply
not attached, keeping bare lfx importable.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any

from langchain_core.callbacks import BaseCallbackHandler

from lfx.observability import APPLICATION_METER_NAME

try:
    from opentelemetry import metrics

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

if TYPE_CHECKING:
    from uuid import UUID

    from langchain_core.outputs import LLMResult


class LLMProviderMetricsCallbackHandler(BaseCallbackHandler):
    """Records outbound LLM provider call duration and errors as leak-safe metrics.

    Thread-safe and keyed by LangChain ``run_id``, so a single shared instance can serve every
    concurrent flow. Attributes are limited to provider, model and (on error) the exception
    class name; nothing derived from prompts, completions or URLs is ever recorded.
    """

    def __init__(self) -> None:
        super().__init__()
        meter = metrics.get_meter(APPLICATION_METER_NAME)
        self._duration = meter.create_histogram(
            "gen_ai.client.operation.duration",
            unit="s",
            description="Duration of outbound LLM provider calls.",
        )
        self._errors = meter.create_counter(
            "gen_ai.client.operation.errors",
            unit="{error}",
            description="Outbound LLM provider call errors, keyed by provider, model and error type.",
        )
        self._lock = threading.Lock()
        self._runs: dict[UUID, tuple[float, dict[str, str]]] = {}

    def _start(self, run_id: UUID, **kwargs: Any) -> None:
        model = _extract_llm_model_name(kwargs)
        provider = _detect_provider_from_model(model)
        attrs = {
            "gen_ai.provider.name": provider or "unknown",
            "gen_ai.request.model": model or "unknown",
        }
        with self._lock:
            self._runs[run_id] = (time.monotonic(), attrs)

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], *, run_id: UUID, **kwargs: Any) -> None:  # noqa: ARG002
        self._start(run_id, **kwargs)

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],  # noqa: ARG002
        messages: list[list[Any]],  # noqa: ARG002
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._start(run_id, **kwargs)

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:  # noqa: ARG002
        with self._lock:
            run = self._runs.pop(run_id, None)
        if run is not None:
            start, attrs = run
            self._duration.record(time.monotonic() - start, attrs)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:  # noqa: ARG002
        with self._lock:
            run = self._runs.pop(run_id, None)
        attrs = run[1] if run is not None else {"gen_ai.provider.name": "unknown", "gen_ai.request.model": "unknown"}
        self._errors.add(1, {**attrs, "error.type": type(error).__name__})


# ponytail: duplicated from langflow native_callback; extract to a shared lfx home if a third copy appears.
def _extract_llm_model_name(kwargs: dict[str, Any]) -> str | None:
    params = kwargs.get("invocation_params") or {}
    return params.get("model_name") or params.get("model") or None


def _detect_provider_from_model(model_name: str | None) -> str | None:
    if not model_name:
        return None
    model_lower = model_name.lower()
    if "gpt" in model_lower or "o1" in model_lower or model_lower.startswith("text-"):
        return "openai"
    if "claude" in model_lower:
        return "anthropic"
    if "gemini" in model_lower or "palm" in model_lower:
        return "google"
    if "llama" in model_lower:
        return "meta"
    if "mistral" in model_lower or "mixtral" in model_lower:
        return "mistral"
    if "command" in model_lower or "coral" in model_lower:
        return "cohere"
    if "titan" in model_lower or "nova" in model_lower:
        return "amazon"
    if "azure" in model_lower:
        return "azure"
    return None


_handler: LLMProviderMetricsCallbackHandler | None = None
_handler_lock = threading.Lock()


def get_llm_provider_metrics_handler() -> LLMProviderMetricsCallbackHandler | None:
    """Return the shared handler, or None when OpenTelemetry is not installed.

    run_ids are unique UUIDs, so one lazily-created shared instance safely serves every flow.
    """
    if not _OTEL_AVAILABLE:
        return None
    global _handler  # noqa: PLW0603
    if _handler is None:
        with _handler_lock:
            if _handler is None:
                _handler = LLMProviderMetricsCallbackHandler()
    return _handler
