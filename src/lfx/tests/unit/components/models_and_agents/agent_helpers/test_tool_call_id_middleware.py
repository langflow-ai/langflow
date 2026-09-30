"""Regression tests for missing model-generated tool-call IDs."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ExtendedModelResponse, ModelResponse, ToolRetryMiddleware
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from lfx.components.models_and_agents.agent_helpers.tool_call_id_middleware import ToolCallIDMiddleware


class ToolCapableFakeChat(FakeMessagesListChatModel):
    def bind_tools(self, _tools, **_kwargs):  # type: ignore[override]
        return self


def _message_with_missing_id(*, content_id: str | None = None, tool_name: str = "known_tool") -> AIMessage:
    return AIMessage(
        content=[{"type": "tool_use", "id": content_id, "name": tool_name, "input": {}}],
        tool_calls=[{"id": None, "name": tool_name, "args": {}, "type": "tool_call"}],
    )


@tool
def known_tool() -> str:
    """Return a successful tool result."""
    return "ok"


def test_should_recover_tool_call_id_from_anthropic_content() -> None:
    message = _message_with_missing_id(content_id="toolu_anthropic_123")

    result = ToolCallIDMiddleware().wrap_model_call(MagicMock(), MagicMock(return_value=message))

    assert result.tool_calls[0]["id"] == "toolu_anthropic_123"
    assert message.tool_calls[0]["id"] is None


def test_should_generate_id_and_keep_structured_content_in_sync_when_both_are_missing() -> None:
    message = _message_with_missing_id()

    result = ToolCallIDMiddleware().wrap_model_call(MagicMock(), MagicMock(return_value=message))

    generated_id = result.tool_calls[0]["id"]
    assert isinstance(generated_id, str)
    assert generated_id.startswith("call_")
    assert result.content[0]["id"] == generated_id
    assert message.tool_calls[0]["id"] is None
    assert message.content[0]["id"] is None


def test_should_preserve_response_identity_when_all_ids_are_valid() -> None:
    message = AIMessage(
        content="",
        tool_calls=[{"id": "call_existing", "name": "known_tool", "args": {}, "type": "tool_call"}],
    )
    response = ModelResponse(result=[message])

    result = ToolCallIDMiddleware().wrap_model_call(MagicMock(), MagicMock(return_value=response))

    assert result is response


def test_should_normalize_ids_inside_extended_model_response() -> None:
    message = _message_with_missing_id()
    response = ExtendedModelResponse(model_response=ModelResponse(result=[message]), command=None)

    result = ToolCallIDMiddleware().wrap_model_call(MagicMock(), MagicMock(return_value=response))

    assert isinstance(result.model_response.result[0].tool_calls[0]["id"], str)


def test_should_prevent_tool_retry_failure_from_crashing_on_tool_message_validation() -> None:
    message = _message_with_missing_id()
    normalized = ToolCallIDMiddleware().wrap_model_call(MagicMock(), MagicMock(return_value=message))
    tool_call = normalized.tool_calls[0]

    result = ToolRetryMiddleware(max_retries=0)._handle_failure(
        tool_call["name"], tool_call["id"], RuntimeError("boom"), 1
    )

    assert result.status == "error"
    assert result.tool_call_id == tool_call["id"]


def test_should_prevent_invalid_tool_call_from_crashing_on_tool_message_validation() -> None:
    message = _message_with_missing_id(tool_name="missing_tool")
    normalized = ToolCallIDMiddleware().wrap_model_call(MagicMock(), MagicMock(return_value=message))

    result = ToolNode([known_tool])._validate_tool_call(normalized.tool_calls[0])

    assert result is not None
    assert result.status == "error"
    assert result.tool_call_id == normalized.tool_calls[0]["id"]


@pytest.mark.asyncio
async def test_should_normalize_missing_ids_in_async_path() -> None:
    message = _message_with_missing_id()

    result = await ToolCallIDMiddleware().awrap_model_call(MagicMock(), AsyncMock(return_value=message))

    assert isinstance(result.tool_calls[0]["id"], str)


@pytest.mark.asyncio
async def test_should_return_tool_error_to_model_end_to_end_when_id_is_missing() -> None:
    @tool
    def failing_tool() -> str:
        """Always fail so the retry middleware emits an error ToolMessage."""
        msg = "boom"
        raise RuntimeError(msg)

    model = ToolCapableFakeChat(
        responses=[
            _message_with_missing_id(tool_name="failing_tool"),
            AIMessage(content="Recovered after the tool error."),
        ]
    )
    graph = create_agent(
        model=model,
        tools=[failing_tool],
        middleware=[ToolCallIDMiddleware(), ToolRetryMiddleware(max_retries=0)],
    )

    result = await graph.ainvoke({"messages": [{"role": "user", "content": "Use the failing tool."}]})

    error_message = next(message for message in result["messages"] if isinstance(message, ToolMessage))
    assert error_message.status == "error"
    assert error_message.tool_call_id.startswith("call_")
    assert result["messages"][-1].content == "Recovered after the tool error."


@pytest.mark.asyncio
async def test_should_return_invalid_tool_error_to_model_end_to_end_when_id_is_missing() -> None:
    model = ToolCapableFakeChat(
        responses=[
            _message_with_missing_id(tool_name="missing_tool"),
            AIMessage(content="Recovered after the invalid tool call."),
        ]
    )
    graph = create_agent(
        model=model,
        tools=[known_tool],
        middleware=[ToolCallIDMiddleware()],
    )

    result = await graph.ainvoke({"messages": [{"role": "user", "content": "Use an unavailable tool."}]})

    error_message = next(message for message in result["messages"] if isinstance(message, ToolMessage))
    assert error_message.status == "error"
    assert error_message.tool_call_id.startswith("call_")
    assert result["messages"][-1].content == "Recovered after the invalid tool call."
