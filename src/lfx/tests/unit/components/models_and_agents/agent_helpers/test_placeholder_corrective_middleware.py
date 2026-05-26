"""Tests for WatsonXPlaceholderMiddleware — corrective re-invoke on placeholder tool args.

The legacy `create_granite_agent` had `_handle_placeholder_in_response` doing
this. This middleware ports that protection so AgentComponent stays robust on
WatsonX models on the new `langchain.agents.create_agent` path.
"""

from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain.agents.middleware import ExtendedModelResponse, ModelResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from lfx.components.models_and_agents.agent_helpers.placeholder_corrective_middleware import (
    WatsonXPlaceholderMiddleware,
)


@dataclass
class _DataclassRequest:
    """A `@dataclass` request stub for the dataclasses.replace fallback branch.

    Exercises `_corrective_request` when no `override()` callable is present
    (the `override()` attribute is intentionally absent on this dataclass).
    """

    messages: list[BaseMessage] = field(default_factory=list)


def _ai_message(*, tool_calls: list[dict] | None = None, content: str = "") -> AIMessage:
    return AIMessage(content=content, tool_calls=tool_calls or [])


def _placeholder_tool_call() -> dict:
    return {
        "id": "call_1",
        "name": "search",
        "args": {"query": "<result-from-previous-search>"},
        "type": "tool_call",
    }


def _placeholder_string_args_tool_call() -> dict:
    """Tool call where `args` is a JSON string (not a dict) with a placeholder inside.

    Some watsonx-hosted models emit `args` as a literal JSON string with the
    placeholder embedded inline rather than as a parsed dict. `detect_placeholder_in_args`
    handles this shape too — exercise it here so the legacy parity claim is enforced.
    """
    return {
        "id": "call_3",
        "name": "search",
        "args": '{"query": "<result-from-previous-search>"}',
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


def test_should_re_invoke_when_placeholder_appears_in_string_form_args() -> None:
    """Re-invokes correctively when tool-call `args` is a string with a placeholder.

    Legacy `_handle_placeholder_in_response` accepted both dict-shaped and
    string-shaped `args`. This middleware is meant to be at parity, so the
    string-args branch must trigger the corrective re-invoke too.

    `AIMessage.tool_calls.args` is dict-typed at the pydantic boundary, but in
    practice some watsonx responses arrive with raw JSON-string args before any
    upstream parser normalizes them — `detect_placeholder_in_args` covers that
    branch, so we use `model_construct()` to bypass schema validation and feed
    the raw shape end-to-end through the middleware.
    """
    middleware = WatsonXPlaceholderMiddleware()
    bad_msg = AIMessage.model_construct(content="", tool_calls=[_placeholder_string_args_tool_call()])
    bad_response = ModelResponse(result=[bad_msg])
    good_response = ModelResponse(result=[_ai_message(content="final")])
    handler = MagicMock(side_effect=[bad_response, good_response])

    result = middleware.wrap_model_call(_request_with_messages([]), handler)

    assert result is good_response
    assert handler.call_count == 2


def test_should_use_dataclasses_replace_when_request_has_no_override() -> None:
    """Falls back to `dataclasses.replace` when the request exposes no `override()`.

    Used for plain `@dataclass` requests (e.g., light test stubs or pre-`override()`
    langchain versions). Verify the request is rebuilt immutably — never mutated
    in place, since callbacks/streaming consumers may hold the reference.
    """
    middleware = WatsonXPlaceholderMiddleware()
    bad_response = ModelResponse(result=[_ai_message(tool_calls=[_placeholder_tool_call()])])
    good_response = ModelResponse(result=[_ai_message(content="final")])
    handler = MagicMock(side_effect=[bad_response, good_response])

    request = _DataclassRequest(messages=[HumanMessage(content="hi")])
    middleware.wrap_model_call(request, handler)

    # Original request is left alone — immutability check.
    assert len(request.messages) == 1
    # The second handler call carried a brand-new request with the corrective.
    second_request = handler.call_args_list[1].args[0]
    assert second_request is not request
    assert len(second_request.messages) == 2
    assert isinstance(second_request.messages[-1], SystemMessage)


def test_should_raise_when_request_supports_neither_override_nor_replace() -> None:
    """Raises loudly when the request is neither a dataclass nor exposes `override()`.

    Production code no longer carries a `setattr` fallback. A request that
    supports neither path should fail with a clear error so the bug is visible,
    instead of silently mutating the caller's object.
    """
    middleware = WatsonXPlaceholderMiddleware()
    bad_response = ModelResponse(result=[_ai_message(tool_calls=[_placeholder_tool_call()])])
    handler = MagicMock(return_value=bad_response)

    bare_request = SimpleNamespace(messages=[HumanMessage(content="hi")])
    with pytest.raises(TypeError):
        middleware.wrap_model_call(bare_request, handler)


@pytest.mark.asyncio
async def test_should_re_invoke_in_async_path_too() -> None:
    middleware = WatsonXPlaceholderMiddleware()
    bad_response = ModelResponse(result=[_ai_message(tool_calls=[_placeholder_tool_call()])])
    good_response = ModelResponse(result=[_ai_message(content="final")])
    handler = AsyncMock(side_effect=[bad_response, good_response])

    result = await middleware.awrap_model_call(_request_with_messages([]), handler)

    assert result is good_response
    assert handler.call_count == 2
