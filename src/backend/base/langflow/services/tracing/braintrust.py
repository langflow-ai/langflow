"""Braintrust tracer for Langflow.

Implements Langflow's BaseTracer interface to send component-level and
LangChain-level traces to Braintrust.

Only depends on the ``braintrust`` package.

Activation: set the BRAINTRUST_API_KEY environment variable.
Optional: BRAINTRUST_API_URL, BRAINTRUST_PROJECT.
"""

from __future__ import annotations

import os
import time
import types
from typing import TYPE_CHECKING, Any
from uuid import UUID as PyUUID

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs.llm_result import LLMResult
from lfx.log.logger import logger
from typing_extensions import override

from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from langchain_core.agents import AgentAction, AgentFinish
    from lfx.graph.vertex.base import Vertex

    from langflow.services.tracing.schema import Log


# ---------------------------------------------------------------------------
# Inline LangChain callback handler (braintrust SDK only, no braintrust-langchain)
# ---------------------------------------------------------------------------


class _BraintrustLangChainHandler(BaseCallbackHandler):
    """Minimal LangChain callback handler that logs spans via the braintrust SDK.

    This is intentionally kept lightweight.  It traces LLM / chat-model calls,
    chains, tools, and retrievers — capturing inputs, outputs, token metrics
    and time-to-first-token — using only ``braintrust.Span.start_span``,
    ``Span.log``, and ``Span.end``.
    """

    def __init__(self, parent_span: Any) -> None:
        self._parent_span = parent_span
        self._spans: dict[PyUUID, Any] = {}
        self._start_times: dict[PyUUID, float] = {}
        self._first_token_times: dict[PyUUID, float] = {}

    # -- helpers -----------------------------------------------------------

    def _start(
        self,
        run_id: PyUUID,
        parent_run_id: PyUUID | None,
        name: str,
        span_type: str | None = None,
        *,
        input: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        from braintrust import SpanTypeAttribute

        parent = self._spans.get(parent_run_id) if parent_run_id else None  # type: ignore[arg-type]
        parent = parent or self._parent_span

        type_attr = None
        if span_type == "llm":
            type_attr = SpanTypeAttribute.LLM
        elif span_type == "tool":
            type_attr = SpanTypeAttribute.TOOL
        elif span_type == "function":
            type_attr = SpanTypeAttribute.FUNCTION
        elif span_type == "task":
            type_attr = SpanTypeAttribute.TASK

        span = parent.start_span(
            name=name,
            type=type_attr,
            input=input,
            metadata=metadata or {},
        )
        self._spans[run_id] = span

    def _end(
        self,
        run_id: PyUUID,
        *,
        output: Any = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        span = self._spans.pop(run_id, None)
        if span is None:
            return
        span.log(
            output=output,
            error=error,
            metadata=metadata or {},
            metrics=metrics or {},
        )
        span.end()

    # -- LLM / Chat Model -------------------------------------------------

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: PyUUID,
        parent_run_id: PyUUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        name: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._start_times[run_id] = time.perf_counter()
        resolved_name = name or serialized.get("name") or _last(serialized.get("id")) or "LLM"
        self._start(
            run_id,
            parent_run_id,
            resolved_name,
            span_type="llm",
            input=prompts,
            metadata={"serialized": serialized, "name": name, "metadata": metadata, **(kwargs or {})},
        )

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: PyUUID,
        parent_run_id: PyUUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        name: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._start_times[run_id] = time.perf_counter()
        resolved_name = name or serialized.get("name") or _last(serialized.get("id")) or "Chat Model"
        self._start(
            run_id,
            parent_run_id,
            resolved_name,
            span_type="llm",
            input=messages,
            metadata={"serialized": serialized, "name": name, "metadata": metadata, **(kwargs or {})},
        )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: PyUUID,
        parent_run_id: PyUUID | None = None,
        **kwargs: Any,
    ) -> None:
        metrics = _extract_token_metrics(response)

        # Time-to-first-token
        first_token_time = self._first_token_times.pop(run_id, None)
        start_time = self._start_times.pop(run_id, None)
        if first_token_time is not None and start_time is not None:
            metrics["time_to_first_token"] = first_token_time - start_time

        model_name = _extract_model_name(response)
        self._end(
            run_id,
            output=response,
            metadata={"model": model_name, **kwargs} if model_name else kwargs,
            metrics=metrics,
        )

    def on_llm_error(self, error: BaseException, *, run_id: PyUUID, **kwargs: Any) -> None:
        self._start_times.pop(run_id, None)
        self._first_token_times.pop(run_id, None)
        self._end(run_id, error=str(error))

    def on_llm_new_token(self, token: str, *, run_id: PyUUID, **kwargs: Any) -> None:
        if run_id not in self._first_token_times:
            self._first_token_times[run_id] = time.perf_counter()

    # -- Chains ------------------------------------------------------------

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: PyUUID,
        parent_run_id: PyUUID | None = None,
        tags: list[str] | None = None,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if tags and "langsmith:hidden" in tags:
            return
        resolved_name = (
            name
            or (metadata or {}).get("langgraph_node")
            or serialized.get("name")
            or _last(serialized.get("id"))
            or "Chain"
        )
        self._start(
            run_id,
            parent_run_id,
            resolved_name,
            span_type="task",
            input=inputs,
            metadata={"serialized": serialized, "name": name, "metadata": metadata, **(kwargs or {})},
        )

    def on_chain_end(self, outputs: dict[str, Any], *, run_id: PyUUID, **kwargs: Any) -> None:
        self._end(run_id, output=outputs)

    def on_chain_error(self, error: BaseException, *, run_id: PyUUID, **kwargs: Any) -> None:
        self._end(run_id, error=str(error))

    # -- Tools -------------------------------------------------------------

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: PyUUID,
        parent_run_id: PyUUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        name: str | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_name = name or serialized.get("name") or _last(serialized.get("id")) or "Tool"
        self._start(
            run_id,
            parent_run_id,
            resolved_name,
            span_type="tool",
            input=inputs or input_str,
            metadata={"serialized": serialized, "name": name, "metadata": metadata, **(kwargs or {})},
        )

    def on_tool_end(self, output: Any, *, run_id: PyUUID, **kwargs: Any) -> None:
        self._end(run_id, output=output)

    def on_tool_error(self, error: BaseException, *, run_id: PyUUID, **kwargs: Any) -> None:
        self._end(run_id, error=str(error))

    # -- Retriever ---------------------------------------------------------

    def on_retriever_start(
        self,
        serialized: dict[str, Any],
        query: str,
        *,
        run_id: PyUUID,
        parent_run_id: PyUUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        name: str | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_name = name or serialized.get("name") or _last(serialized.get("id")) or "Retriever"
        self._start(
            run_id,
            parent_run_id,
            resolved_name,
            span_type="function",
            input=query,
            metadata={"serialized": serialized, "name": name, "metadata": metadata, **(kwargs or {})},
        )

    def on_retriever_end(self, documents: Sequence[Document], *, run_id: PyUUID, **kwargs: Any) -> None:
        self._end(run_id, output=documents)

    def on_retriever_error(self, error: BaseException, *, run_id: PyUUID, **kwargs: Any) -> None:
        self._end(run_id, error=str(error))

    # -- Agent -------------------------------------------------------------

    def on_agent_action(self, action: AgentAction, *, run_id: PyUUID, parent_run_id: PyUUID | None = None, **kwargs: Any) -> None:
        self._start(run_id, parent_run_id, action.tool, span_type="tool", input=action)

    def on_agent_finish(self, finish: AgentFinish, *, run_id: PyUUID, **kwargs: Any) -> None:
        self._end(run_id, output=finish)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _last(items: list[Any] | None) -> Any:
    return items[-1] if items else None


def _extract_token_metrics(response: LLMResult) -> dict[str, Any]:
    """Pull token usage out of an LLMResult."""
    metrics: dict[str, Any] = {}
    for generations in response.generations or []:
        for generation in generations or []:
            message = getattr(generation, "message", None)
            if not message:
                continue
            usage = getattr(message, "usage_metadata", None)
            if usage and isinstance(usage, dict):
                metrics.update(
                    {
                        k: v
                        for k, v in {
                            "total_tokens": usage.get("total_tokens"),
                            "prompt_tokens": usage.get("input_tokens"),
                            "completion_tokens": usage.get("output_tokens"),
                        }.items()
                        if v is not None
                    }
                )
    if not metrics:
        llm_output: dict[str, Any] = response.llm_output or {}
        metrics = llm_output.get("token_usage") or llm_output.get("estimatedTokens") or {}
    return metrics


def _extract_model_name(response: LLMResult) -> str | None:
    for generations in response.generations or []:
        for generation in generations or []:
            message = getattr(generation, "message", None)
            if not message:
                continue
            resp_meta = getattr(message, "response_metadata", None)
            if resp_meta and isinstance(resp_meta, dict):
                name = resp_meta.get("model_name")
                if name:
                    return name
    llm_output: dict[str, Any] = response.llm_output or {}
    return llm_output.get("model_name") or llm_output.get("model") or None


# ---------------------------------------------------------------------------
# Main tracer
# ---------------------------------------------------------------------------


class BraintrustTracer(BaseTracer):
    """Traces Langflow flow executions to Braintrust.

    This tracer creates a root span for each flow run and child spans for
    each component execution.  It also returns a LangChain callback handler
    from ``get_langchain_callback`` so that LangChain-level operations (LLM
    calls, tool usage, retriever queries) are traced with full detail
    including token metrics and time-to-first-token.

    Only depends on the ``braintrust`` package (no ``braintrust-langchain``).
    """

    flow_id: str

    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: PyUUID,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.trace_id = trace_id
        self.user_id = user_id
        self.session_id = session_id
        self.flow_id = trace_name.split(" - ")[-1]
        self.spans: dict[str, Any] = {}

        config = self._get_config()
        self._ready: bool = self._setup_braintrust(config, project_name) if config else False

    @property
    def ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_braintrust(self, config: dict[str, Any], project_name: str) -> bool:
        try:
            from braintrust import init_logger

            project = config.pop("project", None) or project_name or "Langflow"
            self._logger = init_logger(
                project=project,
                api_key=config.get("api_key"),
                app_url=config.get("api_url"),
            )

            # Create a root span for this flow execution
            self._root_span = self._logger.start_span(
                name=self.flow_id,
                input={
                    "trace_name": self.trace_name,
                    "trace_type": self.trace_type,
                },
                metadata={
                    "langflow_trace_id": str(self.trace_id),
                    "langflow_trace_name": self.trace_name,
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                    "created_from": "langflow",
                },
            )
        except ImportError:
            logger.exception("Could not import braintrust. Please install it with `pip install braintrust`.")
            return False
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error setting up Braintrust tracer: {e}")
            return False

        return True

    # ------------------------------------------------------------------
    # BaseTracer interface
    # ------------------------------------------------------------------

    @override
    def add_trace(
        self,
        trace_id: str,
        trace_name: str,
        trace_type: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        vertex: Vertex | None = None,
    ) -> None:
        if not self._ready:
            return

        name = trace_name.removesuffix(f" ({trace_id})")
        processed_inputs = self._convert_to_loggable(inputs) if inputs else {}
        processed_metadata = self._convert_to_loggable(metadata) if metadata else {}

        processed_metadata["from_langflow_component"] = True
        processed_metadata["component_id"] = trace_id
        if trace_type:
            processed_metadata["trace_type"] = trace_type

        span = self._root_span.start_span(
            name=name,
            input=processed_inputs,
            metadata=processed_metadata,
        )

        self.spans[trace_id] = span

    @override
    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: Sequence[Log | dict] = (),
    ) -> None:
        if not self._ready:
            return

        span = self.spans.pop(trace_id, None)
        if span is None:
            logger.warning(f"Braintrust: no span found for trace_id={trace_id}")
            return

        output: dict[str, Any] = {}
        output |= self._convert_to_loggable(outputs) if outputs else {}
        if logs:
            output["logs"] = [self._convert_to_loggable(log) if isinstance(log, dict) else str(log) for log in logs]

        span.log(
            output=output,
            error=str(error) if error else None,
        )
        span.end()

    @override
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._ready:
            return

        self._root_span.log(
            input=self._convert_to_loggable(inputs) if inputs else {},
            output=self._convert_to_loggable(outputs) if outputs else {},
            error=str(error) if error else None,
            metadata=self._convert_to_loggable(metadata) if metadata else {},
        )
        self._root_span.end()

    @override
    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        if not self._ready:
            return None

        # Use the most recent open span as parent so LangChain traces
        # nest under the current component span.
        parent_span = (
            self.spans[next(reversed(self.spans))]
            if self.spans
            else self._root_span
        )
        return _BraintrustLangChainHandler(parent_span)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _convert_to_loggable(self, value: Any) -> Any:
        """Recursively convert Langflow/LangChain types to JSON-serializable values."""
        if isinstance(value, dict):
            return {str(k): self._convert_to_loggable(v) for k, v in value.items() if k is not None}
        if isinstance(value, list):
            return [self._convert_to_loggable(v) for v in value]
        if isinstance(value, Message):
            return value.text
        if isinstance(value, Data):
            return value.get_text()
        if isinstance(value, (BaseMessage, HumanMessage, SystemMessage)):
            return value.content
        if isinstance(value, Document):
            return value.page_content
        if isinstance(value, (types.GeneratorType, types.NoneType)):
            return str(value)
        return value

    @staticmethod
    def _get_config() -> dict[str, Any]:
        """Read Braintrust configuration from environment variables.

        Returns an empty dict if the required BRAINTRUST_API_KEY is not set.
        """
        api_key = os.getenv("BRAINTRUST_API_KEY")
        if not api_key:
            return {}

        config: dict[str, Any] = {"api_key": api_key}

        api_url = os.getenv("BRAINTRUST_API_URL")
        if api_url:
            config["api_url"] = api_url

        project = os.getenv("BRAINTRUST_PROJECT")
        if project:
            config["project"] = project

        return config
