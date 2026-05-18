"""Thread-safe callback handler that accumulates token usage across multiple LLM calls in an agent run."""

import threading

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from lfx.schema.properties import Usage
from lfx.schema.token_usage import extract_usage_from_llm_result  # single source of truth for LLMResult extraction


class TokenUsageCallbackHandler(BaseCallbackHandler):
    """Accumulates token usage from all LLM calls made during an agent execution.

    Agents typically make multiple LLM calls (reasoning + tool use), so this handler
    sums up input/output tokens across all on_llm_end invocations.
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._has_data: bool = False

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:  # noqa: ARG002
        usage = extract_usage_from_llm_result(response)
        if usage:
            with self._lock:
                self._total_input_tokens += usage.input_tokens or 0
                self._total_output_tokens += usage.output_tokens or 0
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
