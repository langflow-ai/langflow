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
from langchain.agents.middleware import ExtendedModelResponse, ModelResponse
from langchain_core.messages import AIMessage, ToolMessage
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
    response = ModelResponse(result=[multi_call])
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(MagicMock(), handler)

    final_msg = result.result[0]
    assert len(final_msg.tool_calls) == 1
    assert final_msg.tool_calls[0]["name"] == "calculator"


def test_should_pass_through_unchanged_when_response_has_one_tool_call() -> None:
    middleware = SingleToolCallMiddleware()
    single_call = _ai_message_with_tool_calls("calculator")
    response = ModelResponse(result=[single_call])
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(MagicMock(), handler)

    assert result is response
    assert result.result[0] is single_call


def test_should_pass_through_unchanged_when_response_has_no_tool_calls() -> None:
    middleware = SingleToolCallMiddleware()
    final = AIMessage(content="just a final answer")
    response = ModelResponse(result=[final])
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(MagicMock(), handler)

    assert result.result[0] is final


def test_should_pass_through_unchanged_when_result_has_no_messages() -> None:
    middleware = SingleToolCallMiddleware()
    response = ModelResponse(result=[])
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(MagicMock(), handler)

    assert result.result == []


def test_should_not_mutate_original_ai_message_in_place() -> None:
    """Verify we return a clamped copy and leave the original message untouched.

    Direct attribute assignment on a pydantic v2 BaseModel mutates references
    held by callbacks/streaming.
    """
    middleware = SingleToolCallMiddleware()
    multi_call = _ai_message_with_tool_calls("calculator", "fetch")
    original_tool_calls = list(multi_call.tool_calls)
    response = ModelResponse(result=[multi_call])
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(MagicMock(), handler)

    assert multi_call.tool_calls == original_tool_calls
    assert result.result[0] is not multi_call
    assert len(result.result[0].tool_calls) == 1


def test_should_clamp_when_handler_returns_plain_ai_message() -> None:
    """`wrap_model_call` may return a bare AIMessage; clamp must apply to that shape too.

    Per the AgentMiddleware base class signature.
    """
    middleware = SingleToolCallMiddleware()
    multi_call = _ai_message_with_tool_calls("calculator", "fetch")
    handler = MagicMock(return_value=multi_call)

    result = middleware.wrap_model_call(MagicMock(), handler)

    assert isinstance(result, AIMessage)
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "calculator"
    # Original is not mutated.
    assert len(multi_call.tool_calls) == 2


def test_should_clamp_when_handler_returns_extended_model_response() -> None:
    """`ExtendedModelResponse` wraps a `ModelResponse` — the clamp must reach in."""
    middleware = SingleToolCallMiddleware()
    multi_call = _ai_message_with_tool_calls("calculator", "fetch")
    inner = ModelResponse(result=[multi_call])
    response = ExtendedModelResponse(model_response=inner, command=None)
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(MagicMock(), handler)

    assert isinstance(result, ExtendedModelResponse)
    assert len(result.model_response.result[0].tool_calls) == 1


def test_should_preserve_identity_when_extended_response_already_has_single_tool_call() -> None:
    """Returns the original `ExtendedModelResponse` by identity when nothing changes.

    Allocating a new wrapper when the inner response is unchanged would waste
    allocations and break callers that use referential equality (e.g., caching
    consumers). The clamp must preserve identity in the no-op case.
    """
    middleware = SingleToolCallMiddleware()
    single_call = _ai_message_with_tool_calls("calculator")
    inner = ModelResponse(result=[single_call])
    response = ExtendedModelResponse(model_response=inner, command=None)
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(MagicMock(), handler)

    assert result is response, "expected unchanged ExtendedModelResponse to be returned by identity"


def test_should_log_warning_when_response_shape_is_unrecognized() -> None:
    """Logs a warning when an unknown response shape is encountered.

    If a future langchain version adds a new response shape, the clamp silently
    no-ops. A warning makes the bypass visible instead of letting the user hit
    the raw WatsonX 400 with no signal that the middleware was skipped.
    """
    from unittest.mock import patch

    middleware = SingleToolCallMiddleware()
    unknown_shape = object()
    handler = MagicMock(return_value=unknown_shape)

    with patch("lfx.components.models_and_agents.agent_helpers.single_tool_call_middleware.logger") as mock_logger:
        result = middleware.wrap_model_call(MagicMock(), handler)

    assert result is unknown_shape
    assert mock_logger.warning.called, "expected a warning when response shape is unrecognized"
    warning_args = mock_logger.warning.call_args.args
    assert "unrecognized response shape" in warning_args[0].lower()


def test_should_pass_through_when_last_message_is_not_ai_message() -> None:
    """Defensive: don't crash, don't clamp when last message is not an AIMessage.

    Structured-output paths can append a ToolMessage after the AIMessage.
    """
    middleware = SingleToolCallMiddleware()
    final = AIMessage(content="done")
    tool = ToolMessage(content="result", tool_call_id="x")
    response = ModelResponse(result=[final, tool])
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(MagicMock(), handler)

    assert result is response


@pytest.mark.asyncio
async def test_should_clamp_in_async_path_too() -> None:
    """LangGraph create_agent uses async by default — the async hook must also clamp."""
    from unittest.mock import AsyncMock

    middleware = SingleToolCallMiddleware()
    multi_call = _ai_message_with_tool_calls("calculator", "fetch")
    response = ModelResponse(result=[multi_call])
    handler = AsyncMock(return_value=response)

    result = await middleware.awrap_model_call(MagicMock(), handler)

    final_msg = result.result[0]
    assert len(final_msg.tool_calls) == 1
