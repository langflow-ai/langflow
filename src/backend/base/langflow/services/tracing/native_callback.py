"""Native callback handler for LangChain integration.

This module provides a callback handler that captures LangChain execution events
(LLM calls, tool calls, chain steps, etc.) and stores them as spans in the database.

Note: Many method parameters are unused but required by the LangChain callback interface.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from langchain_classic.callbacks.base import BaseCallbackHandler

if TYPE_CHECKING:
    from collections.abc import Sequence

    from langchain_classic.schema import AgentAction, AgentFinish, LLMResult
    from langchain_core.documents import Document
    from langchain_core.messages import BaseMessage

    from langflow.services.tracing.native import NativeTracer


class NativeCallbackHandler(BaseCallbackHandler):
    """Callback handler that captures LangChain events as spans.

    This handler is returned by NativeTracer.get_langchain_callback() and
    captures detailed execution information including:
    - LLM calls with token usage
    - Tool/function calls
    - Chain executions
    - Retriever operations
    """

    def __init__(self, tracer: NativeTracer, parent_span_id: UUID | None = None) -> None:
        """Initialize the callback handler.

        Args:
            tracer: The NativeTracer instance to report spans to.
            parent_span_id: Optional parent span ID for nested operations.
        """
        super().__init__()
        self.tracer = tracer
        self.parent_span_id = parent_span_id
        # Keyed by LangChain run_id so on_*_end callbacks can look up the matching on_*_start data.
        self._spans: dict[UUID, dict[str, Any]] = {}

    def _resolve_parent_span_id(self, parent_run_id: UUID | None) -> UUID | None:
        """Return the correct parent span ID so nested LangChain calls form a proper tree."""
        if parent_run_id and parent_run_id in self._spans:
            return self._get_span_id(parent_run_id)
        return self.parent_span_id

    def _get_span_id(self, run_id: UUID) -> UUID:
        """Return a stable span ID for a run, creating one on first access so on_*_end always finds it."""
        if run_id not in self._spans:
            self._spans[run_id] = {"span_id": uuid4(), "start_time": datetime.now(timezone.utc)}
        return self._spans[run_id]["span_id"]

    def _get_start_time(self, run_id: UUID) -> datetime:
        """Return the recorded start time for latency calculation, falling back to now if the run is unknown."""
        if run_id in self._spans:
            return self._spans[run_id]["start_time"]
        return datetime.now(timezone.utc)

    def _calculate_latency(self, run_id: UUID) -> int:
        """Compute wall-clock latency in milliseconds so spans have accurate duration data."""
        start_time = self._get_start_time(run_id)
        end_time = datetime.now(timezone.utc)
        return int((end_time - start_time).total_seconds() * 1000)

    def _cleanup_run(self, run_id: UUID) -> None:
        """Release the in-memory span entry to prevent unbounded growth on long-running sessions."""
        self._spans.pop(run_id, None)

    def _extract_name(self, serialized: dict[str, Any], fallback: str) -> str:
        """Extract a display name from a serialized LangChain component dict.

        Tries ``serialized["name"]`` first, then the last element of
        ``serialized["id"]``, and finally falls back to *fallback*.
        """
        serialized = serialized or {}
        return serialized.get("name") or (serialized.get("id", [fallback])[-1] if serialized.get("id") else fallback)

    @staticmethod
    def _extract_llm_model_name(kwargs: dict[str, Any]) -> str | None:
        """Extract the model name from LangChain invocation params.

        Checks ``invocation_params["model_name"]`` first (OpenAI-style), then
        ``invocation_params["model"]`` (Anthropic/generic style).

        Args:
            kwargs: The ``**kwargs`` dict passed to ``on_llm_start`` or
                ``on_chat_model_start`` by the LangChain callback system.

        Returns:
            Model name string, or ``None`` if not present.
        """
        params = kwargs.get("invocation_params") or {}
        return params.get("model_name") or params.get("model") or None

    @staticmethod
    def _detect_provider_from_model(model_name: str | None) -> str | None:
        """Detect provider from model name for gen_ai.provider.name attribute.

        Pattern matching enables provider detection without database lookups or complex
        configuration, making traces self-contained and parseable by observability tools.
        """
        if not model_name:
            return None

        model_lower = model_name.lower()

        # Pattern-based detection works across different LangChain integrations
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

    @staticmethod
    def _build_llm_span_name(operation: str, model_name: str | None) -> str:
        """Format a span name following the OTel semantic convention ``"{operation} {model}"``.

        Args:
            operation: Human-readable operation name (e.g. ``"ChatOpenAI"``).
            model_name: Optional model identifier (e.g. ``"gpt-4o"``).

        Returns:
            ``"{operation} {model_name}"`` when model is known, otherwise just
            ``operation``.
        """
        return f"{operation} {model_name}" if model_name else operation

    def _handle_error(self, run_id: UUID, error: BaseException) -> None:
        """End a span with an error and clean up the run.

        Shared implementation for on_llm_error, on_chain_error,
        on_tool_error, and on_retriever_error.
        """
        span_id = self._get_span_id(run_id)
        latency_ms = self._calculate_latency(run_id)
        self.tracer.end_langchain_span(
            span_id=span_id,
            error=str(error),
            latency_ms=latency_ms,
        )
        self._cleanup_run(run_id)

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,  # noqa: ARG002
        metadata: dict[str, Any] | None = None,  # noqa: ARG002
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts running."""
        span_id = self._get_span_id(run_id)
        operation = self._extract_name(serialized, "LLM")
        model_name = self._extract_llm_model_name(kwargs)
        name = self._build_llm_span_name(operation, model_name)
        provider = self._detect_provider_from_model(model_name)

        self.tracer.add_langchain_span(
            span_id=span_id,
            name=name,
            span_type="llm",
            inputs={"prompts": prompts},
            parent_span_id=self._resolve_parent_span_id(parent_run_id),
            model_name=model_name,
            provider=provider,
        )

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,  # noqa: ARG002
        metadata: dict[str, Any] | None = None,  # noqa: ARG002
        **kwargs: Any,
    ) -> None:
        """Called when chat model starts running."""
        span_id = self._get_span_id(run_id)
        operation = self._extract_name(serialized, "ChatModel")
        model_name = self._extract_llm_model_name(kwargs)
        name = self._build_llm_span_name(operation, model_name)
        provider = self._detect_provider_from_model(model_name)

        # BaseMessage objects are not JSON-serializable; extract only the fields the UI needs.
        formatted_messages = [
            [{"type": m.type, "content": m.content} for m in message_list] for message_list in messages
        ]

        self.tracer.add_langchain_span(
            span_id=span_id,
            name=name,
            span_type="llm",
            inputs={"messages": formatted_messages},
            parent_span_id=self._resolve_parent_span_id(parent_run_id),
            model_name=model_name,
            provider=provider,
        )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Called when LLM ends running."""
        span_id = self._get_span_id(run_id)
        latency_ms = self._calculate_latency(run_id)

        prompt_tokens, completion_tokens, total_tokens = self._extract_token_usage(response)
        outputs = self._extract_generations(response)

        self.tracer.end_langchain_span(
            span_id=span_id,
            outputs=outputs,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        self._cleanup_run(run_id)

    def _extract_token_usage(self, response: LLMResult):
        """Parse token counts from an LLMResult, trying multiple locations for cross-provider compatibility."""
        llm_output = getattr(response, "llm_output", None) or {}
        token_usage = llm_output.get("token_usage", {}) if isinstance(llm_output, dict) else {}
        prompt_tokens = token_usage.get("prompt_tokens")
        completion_tokens = token_usage.get("completion_tokens")
        total_tokens = token_usage.get("total_tokens")

        # llm_output is the legacy location; newer LangChain versions moved usage into generations.
        if not total_tokens:
            generations = getattr(response, "generations", []) or []
            for gen_list in generations:
                for gen in gen_list:
                    # langchain-core standardized location — preferred when available.
                    message = getattr(gen, "message", None)
                    if message is not None:
                        usage = getattr(message, "usage_metadata", None)
                        if usage:
                            _get = usage.get if isinstance(usage, dict) else lambda k, d=None, u=usage: getattr(u, k, d)
                            prompt_tokens = _get("input_tokens") or prompt_tokens
                            completion_tokens = _get("output_tokens") or completion_tokens
                            total_tokens = _get("total_tokens") or total_tokens

                        # Provider-specific fallback (e.g. OpenAI puts usage in response_metadata).
                        if not total_tokens:
                            resp_meta = getattr(message, "response_metadata", None) or {}
                            if isinstance(resp_meta, dict):
                                usage_dict = resp_meta.get("token_usage") or resp_meta.get("usage", {})
                                if isinstance(usage_dict, dict):
                                    prompt_tokens = (
                                        usage_dict.get("prompt_tokens")
                                        or usage_dict.get("input_tokens")
                                        or prompt_tokens
                                    )
                                    completion_tokens = (
                                        usage_dict.get("completion_tokens")
                                        or usage_dict.get("output_tokens")
                                        or completion_tokens
                                    )
                                    total_tokens = usage_dict.get("total_tokens") or total_tokens

                    # Some providers (e.g. Anthropic via older adapters) put usage in generation_info.
                    if not total_tokens:
                        gen_info = getattr(gen, "generation_info", None) or {}
                        if isinstance(gen_info, dict):
                            usage_dict = gen_info.get("token_usage") or gen_info.get("usage", {})
                            if isinstance(usage_dict, dict):
                                prompt_tokens = (
                                    usage_dict.get("prompt_tokens") or usage_dict.get("input_tokens") or prompt_tokens
                                )
                                completion_tokens = (
                                    usage_dict.get("completion_tokens")
                                    or usage_dict.get("output_tokens")
                                    or completion_tokens
                                )
                                total_tokens = usage_dict.get("total_tokens") or total_tokens

                    if total_tokens:
                        break
                if total_tokens:
                    break
        return prompt_tokens, completion_tokens, total_tokens

    def _extract_generations(self, response: LLMResult):
        """Serialize LLMResult generations to a JSON-safe dict for storage in the span outputs field."""
        generations = getattr(response, "generations", []) or []
        return {
            "generations": [
                [
                    {"text": getattr(gen, "text", ""), "generation_info": getattr(gen, "generation_info", None)}
                    for gen in gen_list
                ]
                for gen_list in generations
            ]
        }

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Called when LLM errors."""
        self._handle_error(run_id, error)

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,  # noqa: ARG002
        metadata: dict[str, Any] | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Called when chain starts running."""
        span_id = self._get_span_id(run_id)
        name = self._extract_name(serialized, "Chain")

        self.tracer.add_langchain_span(
            span_id=span_id,
            name=name,
            span_type="chain",
            inputs=inputs or {},
            parent_span_id=self._resolve_parent_span_id(parent_run_id),
        )

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Called when chain ends running."""
        span_id = self._get_span_id(run_id)
        latency_ms = self._calculate_latency(run_id)

        self.tracer.end_langchain_span(
            span_id=span_id,
            outputs=outputs or {},
            latency_ms=latency_ms,
        )
        self._cleanup_run(run_id)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Called when chain errors."""
        self._handle_error(run_id, error)

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,  # noqa: ARG002
        metadata: dict[str, Any] | None = None,  # noqa: ARG002
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Called when tool starts running."""
        span_id = self._get_span_id(run_id)
        name = self._extract_name(serialized, "Tool")

        self.tracer.add_langchain_span(
            span_id=span_id,
            name=name,
            span_type="tool",
            inputs=inputs or {"input": input_str},
            parent_span_id=self._resolve_parent_span_id(parent_run_id),
        )

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Called when tool ends running."""
        span_id = self._get_span_id(run_id)
        latency_ms = self._calculate_latency(run_id)

        self.tracer.end_langchain_span(
            span_id=span_id,
            outputs={"output": str(output) if not isinstance(output, dict) else output},
            latency_ms=latency_ms,
        )
        self._cleanup_run(run_id)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Called when tool errors."""
        self._handle_error(run_id, error)

    def on_agent_action(
        self,
        action: AgentAction,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent takes an action."""
        # Tool calls capture the actual work; a separate span here would duplicate that data.

    def on_agent_finish(
        self,
        finish: AgentFinish,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent finishes."""
        # The enclosing chain span already records the final output, so no additional span is needed.

    def on_retriever_start(
        self,
        serialized: dict[str, Any],
        query: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,  # noqa: ARG002
        metadata: dict[str, Any] | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Called when retriever starts running."""
        span_id = self._get_span_id(run_id)
        name = self._extract_name(serialized, "Retriever")

        self.tracer.add_langchain_span(
            span_id=span_id,
            name=name,
            span_type="retriever",
            inputs={"query": query},
            parent_span_id=self._resolve_parent_span_id(parent_run_id),
        )

    def on_retriever_end(
        self,
        documents: Sequence[Document],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Called when retriever ends running."""
        span_id = self._get_span_id(run_id)
        latency_ms = self._calculate_latency(run_id)

        # Document objects are not JSON-serializable; extract only the fields the UI needs.
        documents = documents or []
        docs_output = [
            {"page_content": getattr(doc, "page_content", ""), "metadata": getattr(doc, "metadata", {})}
            for doc in documents
        ]

        self.tracer.end_langchain_span(
            span_id=span_id,
            outputs={"documents": docs_output},
            latency_ms=latency_ms,
        )
        self._cleanup_run(run_id)

    def on_retriever_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Called when retriever errors."""
        self._handle_error(run_id, error)
