"""LangChain to Pydantic AI Model Adapter.

This adapter allows any LangChain ChatModel to be used with Pydantic AI agents,
supporting both streaming and non-streaming modes.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk
from pydantic_ai.messages import (
    FinishReason,
    ModelMessage,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ToolCallPart,
    ToolCallPartDelta,
)
from pydantic_ai.models import Model, ModelRequestParameters, StreamedResponse
from pydantic_ai.usage import RequestUsage


class LangChainModel(Model):
    """Wrap any LangChain ChatModel so it can be used by Pydantic AI Agents.

    This adapter supports:
    - Normal (non-streaming) calls
    - Streaming text deltas
    - Streaming tool-call name/args deltas
    - Basic usage accounting
    """

    def __init__(self, lc_model: BaseChatModel, name: str | None = None):
        """Initialize the adapter.

        Args:
            lc_model: Any LangChain BaseChatModel instance
            name: Optional name for the model (defaults to model's class name)
        """
        super().__init__()
        self._lc = lc_model
        self._name = name or getattr(lc_model, "model_name", lc_model.__class__.__name__)

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._name

    @property
    def system(self) -> str:
        """Return the provider name (used for telemetry)."""
        prov = getattr(self._lc, "__class__", type(self._lc)).__name__.lower()
        return prov

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: Any | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Non-streaming call: invoke the LangChain model and return a full ModelResponse."""
        # Prepare LangChain messages
        lc_msgs = _pydantic_to_langchain_messages(messages, model_request_parameters)

        # Invoke the LangChain model
        ai_msg = await self._lc.ainvoke(lc_msgs)

        # Convert result into Pydantic AI parts
        parts: list[Any] = []
        if text := (ai_msg.content or ""):
            parts.append(TextPart(content=text))

        # Tool calls become ToolCallPart
        for tc in getattr(ai_msg, "tool_calls", []) or []:
            parts.append(
                ToolCallPart(
                    tool_name=tc.get("name") or "",
                    args=tc.get("args") or {},
                    tool_call_id=tc.get("id"),
                )
            )

        # Build the response object
        return ModelResponse(
            parts=parts,
            model_name=self.model_name,
            timestamp=datetime.now(timezone.utc),
            provider_name=self.system,
            provider_response_id=getattr(ai_msg, "id", None),
            usage=None,
            finish_reason=FinishReason.stop,
        )

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: Any | None,
        model_request_parameters: ModelRequestParameters,
        run_context: Any | None = None,
    ) -> AsyncIterator[StreamedResponse]:
        """Streaming call: yield a StreamedResponse that translates LangChain chunks."""
        lc_msgs = _pydantic_to_langchain_messages(messages, model_request_parameters)
        lc_iter = self._lc.astream(lc_msgs)
        yield _LCStreamedResponse(
            model_request_parameters=model_request_parameters,
            model_name=self.model_name,
            provider_name=self.system,
            ts=datetime.now(timezone.utc),
            lc_iter=lc_iter,
        )


@dataclass
class _LCStreamedResponse(StreamedResponse):
    """StreamedResponse implementation that translates LangChain chunks to Pydantic AI events."""

    model_request_parameters: ModelRequestParameters

    _model_name: str = field(repr=False, default="")
    _provider_name: str | None = field(repr=False, default=None)
    _timestamp: datetime = field(repr=False, default_factory=lambda: datetime.now(timezone.utc))

    # LangChain async iterator (yields AIMessageChunk)
    lc_iter: AsyncIterator[AIMessageChunk] = field(default=None, repr=False)

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model_name

    @property
    def provider_name(self) -> str | None:
        """Return the provider name."""
        return self._provider_name

    @property
    def timestamp(self) -> datetime:
        """Return the timestamp."""
        return self._timestamp

    def __init__(
        self,
        model_request_parameters: ModelRequestParameters,
        model_name: str,
        provider_name: str | None,
        ts: datetime,
        lc_iter: AsyncIterator[AIMessageChunk],
    ):
        """Initialize the streamed response."""
        super().__init__(model_request_parameters=model_request_parameters)
        self._model_name = model_name
        self._provider_name = provider_name
        self._timestamp = ts
        self.lc_iter = lc_iter

    async def _get_event_iterator(self) -> AsyncIterator[Any]:
        """Translate LangChain AIMessageChunk stream into Pydantic AI events.

        Yields:
            Events from the parts manager as text and tool call deltas are processed
        """
        # Initialize usage accounting
        self._usage = RequestUsage()

        try:
            async for chunk in self.lc_iter:
                # Provider response id if present
                self.provider_response_id = getattr(chunk, "id", self.provider_response_id)

                # 1) TEXT STREAM
                token_piece = chunk.content or ""
                if token_piece:
                    maybe_event = self._parts_manager.handle_text_delta(
                        vendor_part_id="content",
                        content=token_piece,
                    )
                    if maybe_event is not None:
                        yield maybe_event

                # 2) TOOL-CALL STREAM
                for tc_chunk in getattr(chunk, "tool_call_chunks", []) or []:
                    tc_id = tc_chunk.id or f"idx-{tc_chunk.index or 0}"
                    name_delta = tc_chunk.name or ""
                    args_delta = tc_chunk.args or ""

                    maybe_event = self._parts_manager.handle_tool_call_delta(
                        vendor_part_id=tc_id,
                        tool_name=name_delta or None,
                        args=args_delta or None,
                        tool_call_id=tc_id,
                    )
                    if maybe_event is not None:
                        yield maybe_event
        finally:
            # Done: set finish reason
            self.finish_reason = "stop"


def _pydantic_to_langchain_messages(
    messages: list[ModelMessage], params: ModelRequestParameters
) -> list:
    """Convert Pydantic AI messages into LangChain message format.

    Args:
        messages: List of Pydantic AI ModelMessage objects
        params: Pydantic AI model request parameters

    Returns:
        List of LangChain message dictionaries
    """
    from pydantic_ai.messages import (
        ModelRequest,
        SystemPromptPart,
        TextPart as MessageTextPart,
        UserPromptPart,
    )

    msgs = []

    # Convert ModelMessage objects to LangChain format
    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, SystemPromptPart):
                    msgs.append({"role": "system", "content": part.content})
                elif isinstance(part, UserPromptPart):
                    msgs.append({"role": "user", "content": part.content})
                elif isinstance(part, MessageTextPart):
                    # Text parts from user or assistant
                    msgs.append({"role": "user", "content": part.content})

    # Fallback to params if no messages (for simple cases)
    if not msgs:
        if params.system or params.instructions:
            sys_text = " ".join([x for x in [params.system, params.instructions] if x])
            msgs.append({"role": "system", "content": sys_text})

        if params.user_text_prompt:
            msgs.append({"role": "user", "content": params.user_text_prompt})

    return msgs
