"""Tests for build_messages_and_runnable — the Language Model component's input contract.

A Language Model chained after an Agent (or another Language Model) receives an
AI-sender Message as its input_value. That input is THIS component's task, so it must
be sent as a user turn: Gemini rejects any request whose last turn is a model turn with
400 "Requests ending with a model turn are not supported".
"""

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from lfx.base.models.chat_result import build_messages_and_runnable
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER


def _chat_model() -> FakeListChatModel:
    """A real LanguageModel; build_messages_and_runnable only passes it through."""
    return FakeListChatModel(responses=["ok"])


def test_should_keep_user_message_as_human_turn() -> None:
    runnable = _chat_model()

    messages, returned = build_messages_and_runnable(
        input_value=Message(text="What is 2+2?", sender=MESSAGE_SENDER_USER),
        system_message=None,
        original_runnable=runnable,
    )

    assert returned is runnable
    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "What is 2+2?"


def test_should_convert_ai_sender_input_to_human_turn_when_chained_from_upstream_component() -> None:
    """An upstream Agent's output must not become the trailing model turn of the request."""
    messages, _ = build_messages_and_runnable(
        input_value=Message(text="Idea: an AI-powered plant sitter.", sender=MESSAGE_SENDER_AI),
        system_message=None,
        original_runnable=_chat_model(),
    )

    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage), "chained input must be sent as a user turn"
    assert not isinstance(messages[0], AIMessage)
    assert messages[0].content == "Idea: an AI-powered plant sitter."


def test_should_end_with_human_turn_when_ai_sender_input_has_system_message() -> None:
    """The system message is prepended, so the AI-sender input is the tail turn."""
    messages, _ = build_messages_and_runnable(
        input_value=Message(text="Idea: an AI-powered plant sitter.", sender=MESSAGE_SENDER_AI),
        system_message="You are a business analyst.",
        original_runnable=_chat_model(),
    )

    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[-1], HumanMessage), "request must never end with a model turn"
