"""Clamp multi-tool-call AIMessages down to a single tool call.

WatsonX-hosted models (Granite, llama-via-watsonx, etc.) reject requests where the
assistant turn carries more than one tool_call at a time:

    "This model only supports single tool-calls at once!"

The legacy `create_granite_agent` (in `langchain_utilities/ibm_granite_handler.py`)
worked around this by post-processing each model response with `_limit_to_single_tool_call`.
This middleware ports the same protection to the new `langchain.agents.create_agent`
path so AgentComponent works with WatsonX models.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    ExtendedModelResponse,
    ModelResponse,
)
from langchain_core.messages import AIMessage


class SingleToolCallMiddleware(AgentMiddleware):
    """Keep only the first tool call when a model emits several in one turn."""

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        return _clamp(handler(request))

    async def awrap_model_call(self, request: Any, handler: Any) -> Any:
        return _clamp(await handler(request))


def _clamp(response: Any) -> Any:
    # `wrap_model_call` may return any of three shapes (per AgentMiddleware
    # signature): ModelResponse, AIMessage, or ExtendedModelResponse. Older
    # versions of this middleware only handled ModelResponse, so a handler
    # returning AIMessage (e.g. ToolRetryMiddleware on a fallback path) would
    # silently bypass the clamp. Cover all three.
    if isinstance(response, ExtendedModelResponse):
        new_inner = _clamp(response.model_response)
        if new_inner is response.model_response:
            return response
        return replace(response, model_response=new_inner)

    if isinstance(response, ModelResponse):
        new_result = _clamp_message_list(response.result)
        if new_result is response.result:
            return response
        return replace(response, result=new_result)

    if isinstance(response, AIMessage):
        clamped = _clamp_ai_message(response)
        return clamped if clamped is not None else response

    return response


def _clamp_message_list(messages: list[Any]) -> list[Any]:
    if not messages:
        return messages
    last = messages[-1]
    if not isinstance(last, AIMessage):
        return messages
    clamped = _clamp_ai_message(last)
    if clamped is None:
        return messages
    return [*messages[:-1], clamped]


def _clamp_ai_message(message: AIMessage) -> AIMessage | None:
    # Use model_copy instead of `message.tool_calls = ...` — direct assignment
    # bypasses pydantic v2 validators and mutates the object that callbacks /
    # streaming consumers may already hold a reference to.
    tool_calls = message.tool_calls or []
    if len(tool_calls) <= 1:
        return None
    return message.model_copy(update={"tool_calls": tool_calls[:1]})
