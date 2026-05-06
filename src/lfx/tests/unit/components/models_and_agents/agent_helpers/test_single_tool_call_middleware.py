"""Tests for SingleToolCallMiddleware — clamp multi-tool AIMessages down to one.

WatsonX-hosted models (e.g., `meta-llama/llama-3-2-11b-vision-instruct`,
`ibm/granite-*`) reject requests where the assistant turn contains multiple
tool_calls at once with the API error:

    "This model only supports single tool-calls at once!"

The legacy `create_granite_agent` had `_limit_to_single_tool_call` doing this.
This middleware ports that protection so AgentComponent can use the new
`langchain.agents.create_agent` path with WatsonX models.
"""

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage
from lfx.components.models_and_agents.agent_helpers.single_tool_call_middleware import (
    SingleToolCallMiddleware,
)


def _ai_message_with_tool_calls(*tool_call_names: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {"id": f"call_{i}", "name": name, "args": {}, "type": "tool_call"} for i, name in enumerate(tool_call_names)
        ],
    )


def test_should_keep_only_first_tool_call_when_multiple_are_present() -> None:
    middleware = SingleToolCallMiddleware()
    multi_call = _ai_message_with_tool_calls("calculator", "fetch", "search")
    response = MagicMock()
    response.result = [multi_call]
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(MagicMock(), handler)

    final_msg = result.result[0]
    assert len(final_msg.tool_calls) == 1
    assert final_msg.tool_calls[0]["name"] == "calculator"


def test_should_pass_through_unchanged_when_response_has_one_tool_call() -> None:
    middleware = SingleToolCallMiddleware()
    single_call = _ai_message_with_tool_calls("calculator")
    response = MagicMock()
    response.result = [single_call]
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(MagicMock(), handler)

    assert result.result[0].tool_calls == single_call.tool_calls


def test_should_pass_through_unchanged_when_response_has_no_tool_calls() -> None:
    middleware = SingleToolCallMiddleware()
    final = AIMessage(content="just a final answer")
    response = MagicMock()
    response.result = [final]
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(MagicMock(), handler)

    assert result.result[0] is final


def test_should_pass_through_unchanged_when_result_has_no_messages() -> None:
    middleware = SingleToolCallMiddleware()
    response = MagicMock()
    response.result = []
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(MagicMock(), handler)

    assert result.result == []


@pytest.mark.asyncio
async def test_should_clamp_in_async_path_too() -> None:
    """LangGraph create_agent uses async by default — the async hook must also clamp."""
    from unittest.mock import AsyncMock

    middleware = SingleToolCallMiddleware()
    multi_call = _ai_message_with_tool_calls("calculator", "fetch")
    response = MagicMock()
    response.result = [multi_call]
    handler = AsyncMock(return_value=response)

    result = await middleware.awrap_model_call(MagicMock(), handler)

    final_msg = result.result[0]
    assert len(final_msg.tool_calls) == 1
