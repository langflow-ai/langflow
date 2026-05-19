"""OpenInference-aware LangChain callback for Arize Phoenix tracing.

Creates OTEL child spans under the active Langflow component span so agent tool
calls, LLM invocations, and decisions appear nested in Phoenix.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_classic.callbacks.base import BaseCallbackHandler
from openinference.semconv.trace import SpanAttributes

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain_classic.schema import AgentAction, AgentFinish, LLMResult
    from langchain_core.documents import Document
    from langchain_core.messages import BaseMessage
    from opentelemetry.trace import Span

    from langflow.services.tracing.arize_phoenix import ArizePhoenixTracer


class PhoenixCallbackHandler(BaseCallbackHandler):
    """LangChain callback that records nested OTEL spans for Phoenix."""

    def __init__(self, tracer: ArizePhoenixTracer, parent_span: Span) -> None:
        super().__init__()
        self.tracer = tracer
        self.parent_span = parent_span
        self._spans: dict[UUID, Span] = {}

    def _resolve_parent_span(self, parent_run_id: UUID | None) -> Span:
        if parent_run_id and parent_run_id in self._spans:
            return self._spans[parent_run_id]
        return self.parent_span

    def _extract_name(self, serialized: dict[str, Any], fallback: str) -> str:
        serialized = serialized or {}
        return serialized.get("name") or (serialized.get("id", [fallback])[-1] if serialized.get("id") else fallback)

    @staticmethod
    def _extract_llm_model_name(kwargs: dict[str, Any]) -> str | None:
        params = kwargs.get("invocation_params") or {}
        return params.get("model_name") or params.get("model") or None

    @staticmethod
    def _build_llm_span_name(operation: str, model_name: str | None) -> str:
        return f"{operation} {model_name}" if model_name else operation

    def _start_span(
        self,
        run_id: UUID,
        name: str,
        span_kind: str,
        inputs: dict[str, Any],
        parent_run_id: UUID | None,
    ) -> None:
        span = self.tracer.start_langchain_span(
            name=name,
            span_kind=span_kind,
            inputs=inputs,
            parent_span=self._resolve_parent_span(parent_run_id),
        )
        self._spans[run_id] = span

    def _end_span(
        self,
        run_id: UUID,
        outputs: dict[str, Any] | None = None,
        error: BaseException | None = None,
    ) -> None:
        span = self._spans.pop(run_id, None)
        if span is not None:
            self.tracer.end_langchain_span(span, outputs=outputs, error=error)

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
        operation = self._extract_name(serialized, "LLM")
        model_name = self._extract_llm_model_name(kwargs)
        name = self._build_llm_span_name(operation, model_name)
        self._start_span(run_id, name, "llm", {"prompts": prompts}, parent_run_id)
        span = self._spans.get(run_id)
        if span is not None and model_name:
            span.set_attribute(SpanAttributes.LLM_MODEL_NAME, model_name)

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
        operation = self._extract_name(serialized, "ChatModel")
        model_name = self._extract_llm_model_name(kwargs)
        name = self._build_llm_span_name(operation, model_name)
        formatted_messages = [
            [{"type": m.type, "content": m.content} for m in message_list] for message_list in messages
        ]
        self._start_span(run_id, name, "llm", {"messages": formatted_messages}, parent_run_id)
        span = self._spans.get(run_id)
        if span is not None and model_name:
            span.set_attribute(SpanAttributes.LLM_MODEL_NAME, model_name)

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        outputs = self._extract_generations(response)
        self._end_span(run_id, outputs=outputs)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        self._end_span(run_id, error=error)

    def _extract_generations(self, response: LLMResult) -> dict[str, Any]:
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
        name = self._extract_name(serialized, "Chain")
        span_kind = "agent" if "agent" in name.lower() or "AgentExecutor" in name else "chain"
        self._start_span(run_id, name, span_kind, inputs or {}, parent_run_id)

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        self._end_span(run_id, outputs=outputs or {})

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        self._end_span(run_id, error=error)

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
        name = self._extract_name(serialized, "Tool")
        self._start_span(run_id, name, "tool", inputs or {"input": input_str}, parent_run_id)

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        outputs = {"output": str(output) if not isinstance(output, dict) else output}
        self._end_span(run_id, outputs=outputs)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        self._end_span(run_id, error=error)

    def on_agent_action(
        self,
        action: AgentAction,
        *,
        run_id: UUID,  # noqa: ARG002
        parent_run_id: UUID | None = None,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Record agent decisions as short-lived child spans."""
        name = f"Agent Action: {action.tool}"
        inputs = {
            "tool": action.tool,
            "tool_input": action.tool_input,
            "log": action.log,
        }
        span = self.tracer.start_langchain_span(
            name=name,
            span_kind="agent",
            inputs=inputs,
            parent_span=self._resolve_parent_span(parent_run_id),
        )
        self.tracer.end_langchain_span(
            span,
            outputs={"tool": action.tool, "tool_input": action.tool_input},
        )

    def on_agent_finish(
        self,
        finish: AgentFinish,
        *,
        run_id: UUID,  # noqa: ARG002
        parent_run_id: UUID | None = None,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        span = self.tracer.start_langchain_span(
            name="Agent Finish",
            span_kind="agent",
            inputs={"return_values": finish.return_values, "log": finish.log},
            parent_span=self._resolve_parent_span(parent_run_id),
        )
        self.tracer.end_langchain_span(span, outputs={"return_values": finish.return_values})

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
        name = self._extract_name(serialized, "Retriever")
        self._start_span(run_id, name, "retriever", {"query": query}, parent_run_id)

    def on_retriever_end(
        self,
        documents: Sequence[Document],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        documents = documents or []
        docs_output = [
            {"page_content": getattr(doc, "page_content", ""), "metadata": getattr(doc, "metadata", {})}
            for doc in documents
        ]
        self._end_span(run_id, outputs={"documents": docs_output})

    def on_retriever_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        self._end_span(run_id, error=error)
