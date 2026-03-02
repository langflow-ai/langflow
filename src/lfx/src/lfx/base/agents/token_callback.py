"""Thread-safe callback handler that accumulates token usage across multiple LLM calls in an agent run."""

import threading

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


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
                self._total_input_tokens += usage["input_tokens"]
                self._total_output_tokens += usage["output_tokens"]
                self._has_data = True

    def _extract_usage(self, response: LLMResult) -> dict | None:
        """Extract token usage from an LLMResult using multiple strategies.

        Priority order:
        1. LLMResult.llm_output["token_usage"] (OpenAI legacy)
        2. generation.message.usage_metadata (LangChain standard)
        3. generation.message.response_metadata["token_usage"] (OpenAI via LC)
        4. generation.message.response_metadata["usage"] (Anthropic)
        """
        # Strategy 1: llm_output["token_usage"]
        if response.llm_output and "token_usage" in response.llm_output:
            token_usage = response.llm_output["token_usage"]
            input_tokens = token_usage.get("prompt_tokens", 0) or 0
            output_tokens = token_usage.get("completion_tokens", 0) or 0
            if input_tokens or output_tokens:
                return {"input_tokens": input_tokens, "output_tokens": output_tokens}

        # Try generation-level extraction
        for generation_list in response.generations:
            for generation in generation_list:
                message = getattr(generation, "message", None)
                if message is None:
                    continue

                # Strategy 2: usage_metadata (LangChain standard)
                usage_metadata = getattr(message, "usage_metadata", None)
                if usage_metadata and isinstance(usage_metadata, dict):
                    input_tokens = usage_metadata.get("input_tokens", 0) or 0
                    output_tokens = usage_metadata.get("output_tokens", 0) or 0
                    if input_tokens or output_tokens:
                        return {"input_tokens": input_tokens, "output_tokens": output_tokens}

                response_metadata = getattr(message, "response_metadata", None)
                if not response_metadata or not isinstance(response_metadata, dict):
                    continue

                # Strategy 3: response_metadata["token_usage"] (OpenAI via LC)
                if "token_usage" in response_metadata:
                    token_usage = response_metadata["token_usage"]
                    input_tokens = token_usage.get("prompt_tokens", 0) or 0
                    output_tokens = token_usage.get("completion_tokens", 0) or 0
                    if input_tokens or output_tokens:
                        return {"input_tokens": input_tokens, "output_tokens": output_tokens}

                # Strategy 4: response_metadata["usage"] (Anthropic)
                if "usage" in response_metadata:
                    usage = response_metadata["usage"]
                    input_tokens = usage.get("input_tokens", 0) or 0
                    output_tokens = usage.get("output_tokens", 0) or 0
                    if input_tokens or output_tokens:
                        return {"input_tokens": input_tokens, "output_tokens": output_tokens}

        return None

    def get_usage(self) -> dict | None:
        """Return accumulated usage data, or None if no token data was captured."""
        with self._lock:
            if not self._has_data:
                return None
            total = self._total_input_tokens + self._total_output_tokens
            return {
                "input_tokens": self._total_input_tokens,
                "output_tokens": self._total_output_tokens,
                "total_tokens": total,
            }
