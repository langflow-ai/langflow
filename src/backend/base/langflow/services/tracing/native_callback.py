"""Native callback handler for LangChain integration.

This module provides a callback handler that captures LangChain execution events
(LLM calls, tool calls, chain steps, etc.) and stores them as spans in the database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from langchain.callbacks.base import BaseCallbackHandler

if TYPE_CHECKING:
    from langchain.schema import AgentAction, AgentFinish, LLMResult
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
        # Track active spans by run_id
        self._spans: dict[UUID, dict[str, Any]] = {}

    def _get_span_id(self, run_id: UUID) -> UUID:
        """Get or create a span ID for a run."""
        if run_id not in self._spans:
            self._spans[run_id] = {"span_id": uuid4(), "start_time": datetime.now(timezone.utc)}
        return self._spans[run_id]["span_id"]

    def _get_start_time(self, run_id: UUID) -> datetime:
        """Get the start time for a run."""
        if run_id in self._spans:
            return self._spans[run_id]["start_time"]
        return datetime.now(timezone.utc)

    def _calculate_latency(self, run_id: UUID) -> int:
        """Calculate latency in milliseconds for a run."""
        start_time = self._get_start_time(run_id)
        end_time = datetime.now(timezone.utc)
        return int((end_time - start_time).total_seconds() * 1000)

    def _cleanup_run(self, run_id: UUID) -> None:
        """Clean up tracking data for a completed run."""
        self._spans.pop(run_id, None)

    # LLM callbacks
    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts running."""
        span_id = self._get_span_id(run_id)
        serialized = serialized or {}
        name = serialized.get("name") or (serialized.get("id", ["LLM"])[-1] if serialized.get("id") else "LLM")
        model_name = kwargs.get("invocation_params", {}).get("model_name") or kwargs.get("invocation_params", {}).get(
            "model"
        )

        self.tracer.add_langchain_span(
            span_id=span_id,
            name=name,
            span_type="llm",
            inputs={"prompts": prompts},
            parent_span_id=self.parent_span_id or (self._get_span_id(parent_run_id) if parent_run_id else None),
            model_name=model_name,
        )

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when chat model starts running."""
        span_id = self._get_span_id(run_id)
        serialized = serialized or {}
        name = serialized.get("name") or (
            serialized.get("id", ["ChatModel"])[-1] if serialized.get("id") else "ChatModel"
        )
        model_name = kwargs.get("invocation_params", {}).get("model_name") or kwargs.get("invocation_params", {}).get(
            "model"
        )

        # Convert messages to serializable format
        formatted_messages = []
        for message_list in messages:
            formatted_messages.append([{"type": m.type, "content": m.content} for m in message_list])

        self.tracer.add_langchain_span(
            span_id=span_id,
            name=name,
            span_type="llm",
            inputs={"messages": formatted_messages},
            parent_span_id=self.parent_span_id or (self._get_span_id(parent_run_id) if parent_run_id else None),
            model_name=model_name,
        )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM ends running."""
        span_id = self._get_span_id(run_id)
        latency_ms = self._calculate_latency(run_id)

        # Extract token usage
        llm_output = getattr(response, "llm_output", None) or {}
        token_usage = llm_output.get("token_usage", {}) if isinstance(llm_output, dict) else {}
        prompt_tokens = token_usage.get("prompt_tokens")
        completion_tokens = token_usage.get("completion_tokens")
        total_tokens = token_usage.get("total_tokens")

        # Extract generations
        generations = getattr(response, "generations", []) or []
        outputs = {
            "generations": [
                [
                    {"text": getattr(gen, "text", ""), "generation_info": getattr(gen, "generation_info", None)}
                    for gen in gen_list
                ]
                for gen_list in generations
            ]
        }

        self.tracer.end_langchain_span(
            span_id=span_id,
            outputs=outputs,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        self._cleanup_run(run_id)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM errors."""
        span_id = self._get_span_id(run_id)
        latency_ms = self._calculate_latency(run_id)

        self.tracer.end_langchain_span(
            span_id=span_id,
            error=str(error),
            latency_ms=latency_ms,
        )
        self._cleanup_run(run_id)

    # Chain callbacks
    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when chain starts running."""
        span_id = self._get_span_id(run_id)
        serialized = serialized or {}
        name = serialized.get("name") or (serialized.get("id", ["Chain"])[-1] if serialized.get("id") else "Chain")

        self.tracer.add_langchain_span(
            span_id=span_id,
            name=name,
            span_type="chain",
            inputs=inputs or {},
            parent_span_id=self.parent_span_id or (self._get_span_id(parent_run_id) if parent_run_id else None),
        )

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
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
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when chain errors."""
        span_id = self._get_span_id(run_id)
        latency_ms = self._calculate_latency(run_id)

        self.tracer.end_langchain_span(
            span_id=span_id,
            error=str(error),
            latency_ms=latency_ms,
        )
        self._cleanup_run(run_id)

    # Tool callbacks
    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when tool starts running."""
        span_id = self._get_span_id(run_id)
        serialized = serialized or {}
        name = serialized.get("name") or "Tool"

        self.tracer.add_langchain_span(
            span_id=span_id,
            name=name,
            span_type="tool",
            inputs=inputs or {"input": input_str},
            parent_span_id=self.parent_span_id or (self._get_span_id(parent_run_id) if parent_run_id else None),
        )

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
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
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when tool errors."""
        span_id = self._get_span_id(run_id)
        latency_ms = self._calculate_latency(run_id)

        self.tracer.end_langchain_span(
            span_id=span_id,
            error=str(error),
            latency_ms=latency_ms,
        )
        self._cleanup_run(run_id)

    # Agent callbacks
    def on_agent_action(
        self,
        action: AgentAction,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent takes an action."""
        # Agent actions are typically followed by tool calls, so we don't create separate spans

    def on_agent_finish(
        self,
        finish: AgentFinish,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent finishes."""
        # Agent finish is handled by chain end

    # Retriever callbacks
    def on_retriever_start(
        self,
        serialized: dict[str, Any],
        query: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when retriever starts running."""
        span_id = self._get_span_id(run_id)
        serialized = serialized or {}
        name = serialized.get("name") or (
            serialized.get("id", ["Retriever"])[-1] if serialized.get("id") else "Retriever"
        )

        self.tracer.add_langchain_span(
            span_id=span_id,
            name=name,
            span_type="retriever",
            inputs={"query": query},
            parent_span_id=self.parent_span_id or (self._get_span_id(parent_run_id) if parent_run_id else None),
        )

    def on_retriever_end(
        self,
        documents: list[Document],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when retriever ends running."""
        span_id = self._get_span_id(run_id)
        latency_ms = self._calculate_latency(run_id)

        # Serialize documents
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
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when retriever errors."""
        span_id = self._get_span_id(run_id)
        latency_ms = self._calculate_latency(run_id)

        self.tracer.end_langchain_span(
            span_id=span_id,
            error=str(error),
            latency_ms=latency_ms,
        )
        self._cleanup_run(run_id)
