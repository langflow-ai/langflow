"""Regression tests for Anthropic omitted-thinking blocks."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain.agents.middleware import ExtendedModelResponse, ModelResponse
from langchain_core.messages import AIMessage
from lfx.components.models_and_agents.agent_helpers.anthropic_thinking_middleware import (
    AnthropicThinkingMiddleware,
)


def _signature_only_message() -> AIMessage:
    return AIMessage(
        content=[
            {"type": "thinking", "signature": "signed", "index": 0},
            {"type": "tool_use", "id": "tool-1", "name": "search", "input": {}},
        ]
    )


def test_restores_empty_thinking_field_on_omitted_thinking_block() -> None:
    message = _signature_only_message()

    result = AnthropicThinkingMiddleware().wrap_model_call(MagicMock(), MagicMock(return_value=message))

    assert result.content[0] == {"type": "thinking", "thinking": "", "signature": "signed", "index": 0}
    assert result.content[1] == message.content[1]
    assert "thinking" not in message.content[0]


def test_preserves_valid_thinking_block_and_response_identity() -> None:
    message = AIMessage(content=[{"type": "thinking", "thinking": "summary", "signature": "signed"}])
    response = ModelResponse(result=[message])

    result = AnthropicThinkingMiddleware().wrap_model_call(MagicMock(), MagicMock(return_value=response))

    assert result is response


def test_normalizes_model_response() -> None:
    response = ModelResponse(result=[_signature_only_message()])

    result = AnthropicThinkingMiddleware().wrap_model_call(MagicMock(), MagicMock(return_value=response))

    assert result is not response
    assert result.result[0].content[0]["thinking"] == ""


def test_normalizes_extended_model_response() -> None:
    response = ExtendedModelResponse(model_response=ModelResponse(result=[_signature_only_message()]), command=None)

    result = AnthropicThinkingMiddleware().wrap_model_call(MagicMock(), MagicMock(return_value=response))

    assert result is not response
    assert result.model_response.result[0].content[0]["thinking"] == ""


@pytest.mark.asyncio
async def test_normalizes_async_response() -> None:
    result = await AnthropicThinkingMiddleware().awrap_model_call(
        MagicMock(), AsyncMock(return_value=_signature_only_message())
    )

    assert result.content[0]["thinking"] == ""
