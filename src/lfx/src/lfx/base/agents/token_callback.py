"""Thread-safe callback handler that accumulates token usage across multiple LLM calls in an agent run."""

import threading
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

from lfx.schema.properties import Usage
from lfx.schema.token_usage import extract_usage_from_llm_result  # single source of truth for LLMResult extraction

# Chars-per-token approximation. tiktoken would be more accurate but adds a heavy
# dependency for what is a best-effort fallback when the server never returned a
# real usage block (e.g. the call failed with HTTP 429 before completing).
# 4 is the canonical OpenAI rule-of-thumb and is within ~15% for English prompts.
_CHARS_PER_TOKEN = 4


class TokenUsageCallbackHandler(BaseCallbackHandler):
    """Accumulates token usage from all LLM calls made during an agent execution.

    Agents typically make multiple LLM calls (reasoning + tool use), so this handler
    sums up input/output tokens across all on_llm_end invocations.

    When an LLM call fails (e.g. HTTP 429 quota), `on_llm_end` is never called so
    the server-reported usage is unavailable. Without a fallback the failed call
    silently contributes 0 to the total, even though the request body was already
    sent and is billable (QA UI-013). To avoid that under-count, the handler
    estimates input tokens on `on_*_start` and flushes the estimate on
    `on_llm_error` (and discards it on `on_llm_end`, since the real usage wins).
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._has_data: bool = False
        # run_id → pre-call input-token estimate, used only if the call errors out.
        self._pending_input_estimates: dict[UUID, int] = {}

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],  # noqa: ARG002
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        estimate = _estimate_tokens_from_messages(messages)
        if estimate:
            with self._lock:
                self._pending_input_estimates[run_id] = estimate

    def on_llm_start(
        self,
        serialized: dict[str, Any],  # noqa: ARG002
        prompts: list[str],
        *,
        run_id: UUID,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        estimate = _estimate_tokens_from_strings(prompts)
        if estimate:
            with self._lock:
                self._pending_input_estimates[run_id] = estimate

    def on_llm_end(self, response: LLMResult, *, run_id: UUID | None = None, **kwargs) -> None:  # noqa: ARG002
        usage = extract_usage_from_llm_result(response)
        with self._lock:
            # The server-reported numbers are authoritative — drop the pre-call
            # estimate so the same input tokens are not counted twice.
            if run_id is not None:
                self._pending_input_estimates.pop(run_id, None)
            if usage:
                self._total_input_tokens += usage.input_tokens or 0
                self._total_output_tokens += usage.output_tokens or 0
                self._has_data = True

    def on_llm_error(
        self,
        error: BaseException,  # noqa: ARG002
        *,
        run_id: UUID,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        with self._lock:
            estimate = self._pending_input_estimates.pop(run_id, 0)
            if estimate:
                self._total_input_tokens += estimate
                self._has_data = True

    def get_usage(self) -> Usage | None:
        """Return accumulated usage data, or None if no token data was captured."""
        with self._lock:
            if not self._has_data:
                return None
            total = self._total_input_tokens + self._total_output_tokens
            return Usage(
                input_tokens=self._total_input_tokens,
                output_tokens=self._total_output_tokens,
                total_tokens=total,
            )


def _estimate_tokens_from_messages(messages: list[list[BaseMessage]]) -> int:
    total_chars = 0
    for batch in messages or []:
        for message in batch or []:
            content = getattr(message, "content", "")
            total_chars += _content_length(content)
    return total_chars // _CHARS_PER_TOKEN


def _estimate_tokens_from_strings(prompts: list[str]) -> int:
    total_chars = sum(len(p) for p in (prompts or []) if isinstance(p, str))
    return total_chars // _CHARS_PER_TOKEN


def _content_length(content: Any) -> int:
    """Recursively measure string length of a LangChain message content payload.

    Content can be str, list[str | dict], or arbitrary; only text parts are
    counted (binary attachments are NOT billable as tokens in the same way).
    """
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        length = 0
        for part in content:
            if isinstance(part, str):
                length += len(part)
            elif isinstance(part, dict):
                text = part.get("text") if part.get("type") == "text" else None
                if isinstance(text, str):
                    length += len(text)
        return length
    return 0
