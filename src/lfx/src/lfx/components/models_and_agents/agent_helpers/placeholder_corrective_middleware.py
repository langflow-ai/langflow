"""Corrective re-invoke for WatsonX placeholder tool args.

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

Cost note: each placeholder correction consumes an extra model call against
`ModelCallLimitMiddleware.run_limit`. WatsonX agents may therefore exhaust
`max_iterations` faster than non-WatsonX agents on flows that trigger the
corrective path; size `max_iterations` accordingly.
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
    "Re-issue this tool call using the actual values from previous tool results. "
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

    Prefers `ModelRequest.override(...)` (the documented immutable pattern;
    direct attribute assignment is deprecated on `ModelRequest`). Falls back
    to `dataclasses.replace` for plain `@dataclass` requests. We never mutate
    the caller's request in place — callbacks and streaming consumers may hold
    a reference to it.
    """
    corrective_msg = SystemMessage(content=_CORRECTIVE_CONTENT)
    existing = list(getattr(request, "messages", None) or [])
    new_messages = [*existing, corrective_msg]

    override = getattr(request, "override", None)
    if callable(override):
        return override(messages=new_messages)
    return replace(request, messages=new_messages)
