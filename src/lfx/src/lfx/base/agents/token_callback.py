"""Thread-safe callback handler that accumulates token usage across multiple LLM calls in an agent run."""

import threading

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from lfx.schema.properties import Usage
from lfx.schema.token_usage import extract_usage_from_message


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
        usage = self._extract_usage(response)
        if usage:
            with self._lock:
                self._total_input_tokens += usage.input_tokens or 0
                self._total_output_tokens += usage.output_tokens or 0
                self._has_data = True

    def _extract_usage(self, response: LLMResult) -> Usage | None:
        """Extract token usage from an LLMResult using multiple strategies.

        Priority order:
        1. LLMResult.llm_output["token_usage"] (OpenAI legacy — unique to LLMResult)
        2-4. Delegated to extract_usage_from_message() for generation-level extraction
        """
        # Strategy 1: llm_output["token_usage"] (unique to LLMResult, not on messages)
        if response.llm_output and "token_usage" in response.llm_output:
            token_usage = response.llm_output["token_usage"]
            input_tokens = token_usage.get("prompt_tokens", 0) or 0
            output_tokens = token_usage.get("completion_tokens", 0) or 0
            if input_tokens or output_tokens:
                return Usage(input_tokens=input_tokens, output_tokens=output_tokens)

        # Strategies 2-4: delegate to shared extraction from generation messages
        for generation_list in response.generations:
            for generation in generation_list:
                message = getattr(generation, "message", None)
                if message is None:
                    continue
                usage = extract_usage_from_message(message)
                if usage:
                    return usage

        return None

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
