"""Tests for LCModelComponent.build_status_message()."""

from langchain_core.messages import AIMessage
from lfx.base.models.model import LCModelComponent


def _component() -> LCModelComponent:
    return LCModelComponent()


def test_none_token_usage_does_not_raise() -> None:
    """An OpenAI-compatible response without token usage should still produce a status message."""
    message = AIMessage(
        content="hello",
        response_metadata={
            "model_name": "agent/sample",
            "finish_reason": "stop",
            "token_usage": None,
        },
    )
    assert _component().build_status_message(message) == "Response: hello"


def test_none_anthropic_usage_does_not_raise() -> None:
    message = AIMessage(
        content="hello",
        response_metadata={
            "model": "claude",
            "usage": None,
            "stop_reason": "end_turn",
        },
    )
    assert _component().build_status_message(message) == "Response: hello"


def test_valid_token_usage_still_formatted() -> None:
    message = AIMessage(
        content="hello",
        response_metadata={
            "model_name": "agent/sample",
            "finish_reason": "stop",
            "token_usage": {
                "completion_tokens": 2,
                "prompt_tokens": 3,
                "total_tokens": 5,
            },
        },
    )
    result = _component().build_status_message(message)
    assert result["tokens"]["total"] == 5
