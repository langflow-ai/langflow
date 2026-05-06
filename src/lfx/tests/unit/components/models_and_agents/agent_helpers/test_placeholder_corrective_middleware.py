"""Tests for WatsonXPlaceholderMiddleware — corrective re-invoke on placeholder tool args.

The legacy `create_granite_agent` had `_handle_placeholder_in_response` doing
this. This middleware ports that protection so AgentComponent stays robust on
WatsonX models on the new `langchain.agents.create_agent` path.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain.agents.middleware import ExtendedModelResponse, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from lfx.components.models_and_agents.agent_helpers.placeholder_corrective_middleware import (
    WatsonXPlaceholderMiddleware,
)


def _ai_message(*, tool_calls: list[dict] | None = None, content: str = "") -> AIMessage:
    return AIMessage(content=content, tool_calls=tool_calls or [])


def _placeholder_tool_call() -> dict:
    return {
        "id": "call_1",
        "name": "search",
        "args": {"query": "<result-from-previous-search>"},
        "type": "tool_call",
    }


def _clean_tool_call() -> dict:
    return {
        "id": "call_2",
        "name": "search",
        "args": {"query": "real value"},
        "type": "tool_call",
    }


def _request_with_messages(messages: list) -> SimpleNamespace:
    """Lightweight stub mimicking ModelRequest's `messages` + `override`."""
    captured: dict = {}

    def override(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(messages=kwargs.get("messages", messages), override=override, captured=captured)

    return SimpleNamespace(messages=messages, override=override, captured=captured)


def test_should_pass_through_when_no_tool_calls() -> None:
    middleware = WatsonXPlaceholderMiddleware()
    response = ModelResponse(result=[_ai_message(content="final answer")])
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(_request_with_messages([]), handler)

    assert result is response
    assert handler.call_count == 1


def test_should_pass_through_when_tool_args_are_clean() -> None:
    middleware = WatsonXPlaceholderMiddleware()
    response = ModelResponse(result=[_ai_message(tool_calls=[_clean_tool_call()])])
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(_request_with_messages([]), handler)

    assert result is response
    assert handler.call_count == 1


def test_should_re_invoke_with_corrective_message_when_placeholder_in_dict_args() -> None:
    middleware = WatsonXPlaceholderMiddleware()
    bad_response = ModelResponse(result=[_ai_message(tool_calls=[_placeholder_tool_call()])])
    good_response = ModelResponse(result=[_ai_message(content="final answer with real values")])
    handler = MagicMock(side_effect=[bad_response, good_response])
    request = _request_with_messages([HumanMessage(content="hi")])

    result = middleware.wrap_model_call(request, handler)

    assert result is good_response
    assert handler.call_count == 2
    # The second call must carry an appended corrective SystemMessage.
    second_request = handler.call_args_list[1].args[0]
    last_message = second_request.messages[-1]
    assert isinstance(last_message, SystemMessage)
    assert "actual values" in last_message.content


def test_should_only_re_invoke_once_even_if_corrective_response_still_has_placeholders() -> None:
    """No infinite re-invoke loop. If the corrective response is still bad, return it."""
    middleware = WatsonXPlaceholderMiddleware()
    still_bad = ModelResponse(result=[_ai_message(tool_calls=[_placeholder_tool_call()])])
    handler = MagicMock(side_effect=[still_bad, still_bad])

    result = middleware.wrap_model_call(_request_with_messages([]), handler)

    assert result is still_bad
    assert handler.call_count == 2


def test_should_handle_plain_ai_message_response_shape() -> None:
    """`wrap_model_call` may return a bare AIMessage; placeholder check applies."""
    middleware = WatsonXPlaceholderMiddleware()
    bad_msg = _ai_message(tool_calls=[_placeholder_tool_call()])
    good_msg = _ai_message(content="final")
    handler = MagicMock(side_effect=[bad_msg, good_msg])

    result = middleware.wrap_model_call(_request_with_messages([]), handler)

    assert result is good_msg
    assert handler.call_count == 2


def test_should_handle_extended_model_response_shape() -> None:
    middleware = WatsonXPlaceholderMiddleware()
    bad_response = ExtendedModelResponse(
        model_response=ModelResponse(result=[_ai_message(tool_calls=[_placeholder_tool_call()])]),
        command=None,
    )
    good_response = ExtendedModelResponse(
        model_response=ModelResponse(result=[_ai_message(content="ok")]),
        command=None,
    )
    handler = MagicMock(side_effect=[bad_response, good_response])

    result = middleware.wrap_model_call(_request_with_messages([]), handler)

    assert result is good_response
    assert handler.call_count == 2


def test_should_use_request_override_when_available() -> None:
    """Verify we go through `ModelRequest.override()`.

    `ModelRequest` documents `override()` as the immutable update path; direct
    attribute assignment is deprecated.
    """
    middleware = WatsonXPlaceholderMiddleware()
    bad_response = ModelResponse(result=[_ai_message(tool_calls=[_placeholder_tool_call()])])
    good_response = ModelResponse(result=[_ai_message(content="final")])
    handler = MagicMock(side_effect=[bad_response, good_response])

    request = _request_with_messages([HumanMessage(content="hi")])
    middleware.wrap_model_call(request, handler)

    # The original request is left alone (immutability check).
    assert len(request.messages) == 1
    # And override() was called with the new appended messages list.
    assert "messages" in request.captured
    assert len(request.captured["messages"]) == 2
    assert isinstance(request.captured["messages"][-1], SystemMessage)


@pytest.mark.asyncio
async def test_should_re_invoke_in_async_path_too() -> None:
    middleware = WatsonXPlaceholderMiddleware()
    bad_response = ModelResponse(result=[_ai_message(tool_calls=[_placeholder_tool_call()])])
    good_response = ModelResponse(result=[_ai_message(content="final")])
    handler = AsyncMock(side_effect=[bad_response, good_response])

    result = await middleware.awrap_model_call(_request_with_messages([]), handler)

    assert result is good_response
    assert handler.call_count == 2
