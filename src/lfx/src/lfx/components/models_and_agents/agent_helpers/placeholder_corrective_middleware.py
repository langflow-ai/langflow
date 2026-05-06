"""Re-invoke the model with a corrective prompt when WatsonX emits placeholder
syntax in tool arguments.

WatsonX-hosted models occasionally emit literal placeholder strings (e.g.
`<result-from-search>`, `<previous-output>`, `<extracted-value>`) in tool
call arguments instead of using actual values from prior tool results.
Calling the tool with such garbage produces nonsense output and derails
the agent loop.

The legacy `create_granite_agent` path caught this with
`_handle_placeholder_in_response` (in `langchain_utilities/ibm_granite_handler.py`).
This middleware ports the same protection to the new
`langchain.agents.create_agent` path so AgentComponent stays robust on
WatsonX models.

Single-shot correction only: if the corrective re-invoke still emits
placeholders, return that response unchanged so the agent loop doesn't
spin in a re-invoke cycle.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    ExtendedModelResponse,
    ModelResponse,
)
from langchain_core.messages import AIMessage, SystemMessage

from lfx.components.langchain_utilities.ibm_granite_handler import detect_placeholder_in_args
from lfx.log.logger import logger

_CORRECTIVE_CONTENT = (
    "Provide your final answer using the actual values from previous tool results. "
    "Do not use placeholder syntax like <result-from-...> in tool arguments — use the real values."
)


class WatsonXPlaceholderMiddleware(AgentMiddleware):
    """Detect placeholder syntax in tool args and re-invoke once with a corrective prompt."""

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        response = handler(request)
        if not _has_placeholder(response):
            return response
        logger.warning("[WatsonX] Placeholder detected in tool args, re-invoking with corrective prompt")
        return handler(_corrective_request(request))

    async def awrap_model_call(self, request: Any, handler: Any) -> Any:
        response = await handler(request)
        if not _has_placeholder(response):
            return response
        logger.warning("[WatsonX] Placeholder detected in tool args, re-invoking with corrective prompt")
        return await handler(_corrective_request(request))


def _ai_message_from_response(response: Any) -> AIMessage | None:
    if isinstance(response, AIMessage):
        return response
    if isinstance(response, ExtendedModelResponse):
        return _ai_message_from_response(response.model_response)
    if isinstance(response, ModelResponse):
        for msg in reversed(response.result):
            if isinstance(msg, AIMessage):
                return msg
    return None


def _has_placeholder(response: Any) -> bool:
    msg = _ai_message_from_response(response)
    if msg is None:
        return False
    tool_calls = getattr(msg, "tool_calls", None) or []
    if not tool_calls:
        return False
    detected, _ = detect_placeholder_in_args(tool_calls)
    return detected


def _corrective_request(request: Any) -> Any:
    """Append a corrective SystemMessage to the request's messages.

    Prefers `ModelRequest.override(...)` (the documented immutable pattern,
    direct attribute assignment is deprecated on `ModelRequest`). Falls back
    to `dataclasses.replace` and finally to direct setattr so unit tests
    using lightweight stubs still work.
    """
    corrective_msg = SystemMessage(content=_CORRECTIVE_CONTENT)
    existing = list(getattr(request, "messages", None) or [])
    new_messages = [*existing, corrective_msg]

    override = getattr(request, "override", None)
    if callable(override):
        return override(messages=new_messages)
    try:
        return replace(request, messages=new_messages)
    except TypeError:
        request.messages = new_messages
        return request
