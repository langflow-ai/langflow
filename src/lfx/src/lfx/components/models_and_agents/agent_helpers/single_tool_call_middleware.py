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

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage


class SingleToolCallMiddleware(AgentMiddleware):
    """Keep only the first tool call when a model emits several in one turn."""

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        return _clamp(handler(request))

    async def awrap_model_call(self, request: Any, handler: Any) -> Any:
        return _clamp(await handler(request))


def _clamp(response: Any) -> Any:
    messages = getattr(response, "result", None) or []
    if not messages:
        return response

    last = messages[-1]
    if not isinstance(last, AIMessage):
        return response

    tool_calls = getattr(last, "tool_calls", None) or []
    if len(tool_calls) <= 1:
        return response

    last.tool_calls = tool_calls[:1]
    return response
