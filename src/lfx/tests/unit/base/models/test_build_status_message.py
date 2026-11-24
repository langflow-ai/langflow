"""Tests for LCModelComponent.build_status_message.

OpenAI-compatible endpoints that omit the ``usage`` object on the wire surface
as ``response_metadata["token_usage"] = None`` while the call itself succeeds
(GH-16512). The status message must keep the successful response text and omit
the token display instead of raising.
"""

from __future__ import annotations

from collections import UserDict

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from lfx.base.models.model import LCModelComponent


class _MinimalModelComponent(LCModelComponent):
    def build_model(self):
        raise NotImplementedError


class TestBuildStatusMessage:
    @pytest.mark.parametrize("mapping", [dict, UserDict])
    def test_full_openai_metadata_keeps_token_counts(self, mapping):
        component = _MinimalModelComponent()
        message = AIMessage(
            content="hello",
            response_metadata={
                "model_name": "gpt-4o",
                "finish_reason": "stop",
                "token_usage": mapping(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            },
        )

        status = component.build_status_message(message)

        assert status == {
            "tokens": {
                "input": 10,
                "output": 5,
                "total": 15,
                "stop_reason": "stop",
                "response": "hello",
            }
        }

    def test_none_token_usage_keeps_response_text(self):
        # Shape produced by ChatOpenAI when the endpoint's HTTP 200 body omits
        # `usage` (GH-16512): the response is valid, only the counts are missing.
        component = _MinimalModelComponent()
        message = AIMessage(
            content="hello",
            response_metadata={
                "model_name": "agent/sample",
                "finish_reason": "stop",
                "token_usage": None,
            },
        )

        status = component.build_status_message(message)

        assert status == "Response: hello"

    def test_none_anthropic_usage_keeps_response_text(self):
        component = _MinimalModelComponent()
        message = AIMessage(
            content="hello",
            response_metadata={"model": "claude", "stop_reason": "end_turn", "usage": None},
        )

        status = component.build_status_message(message)

        assert status == "Response: hello"

    def test_full_anthropic_metadata_keeps_token_counts(self):
        component = _MinimalModelComponent()
        message = AIMessage(
            content="hello",
            response_metadata={
                "model": "claude",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

        status = component.build_status_message(message)

        assert status == {
            "tokens": {
                "input": 10,
                "output": 5,
                "stop_reason": "end_turn",
                "response": "hello",
            }
        }

    def test_unrecognized_metadata_falls_back_to_response_text(self):
        component = _MinimalModelComponent()
        message = AIMessage(content="hello", response_metadata={"model_name": "other"})

        status = component.build_status_message(message)

        assert status == "Response: hello"


@pytest.mark.asyncio
async def test_chat_result_keeps_text_and_clears_previous_usage():
    component = _MinimalModelComponent()
    metadata = {"model_name": "agent/sample", "finish_reason": "stop"}
    counts = {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}
    model = FakeMessagesListChatModel(
        responses=[
            AIMessage(content="first", response_metadata={**metadata, "token_usage": counts}),
            AIMessage(content="second", response_metadata={**metadata, "token_usage": None}),
        ]
    )

    first = await component.get_chat_result(runnable=model, stream=False, input_value="hi")
    assert first.properties.usage.total_tokens == 3
    assert component._token_usage == first.properties.usage

    second = await component.get_chat_result(runnable=model, stream=False, input_value="hi")
    assert second.text == "second"
    assert component.status == "Response: second"
    assert second.properties.usage is None
    assert component._token_usage is None
