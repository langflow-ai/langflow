"""Tests for build_initial_messages — converts (input_value, chat_history) to list[BaseMessage].

Slice S1-S3 of langchain_classic.AgentExecutor → langchain.agents.create_agent migration.
See CZL/PLAN_create_agent_migration.md.
"""

from unittest.mock import patch

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from lfx.base.agents.messages_input_builder import build_initial_messages
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER


def _content_text(message: BaseMessage) -> str:
    """Extract the textual portion of a BaseMessage's content (string or list-of-parts)."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
        return "".join(parts)
    return ""


def test_should_build_single_human_message_when_no_chat_history() -> None:
    msg = Message(text="What is 2+2?", sender=MESSAGE_SENDER_USER)

    messages = build_initial_messages(input_value=msg, chat_history=None)

    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "What is 2+2?"


def test_should_prepend_chat_history_when_provided() -> None:
    msg = Message(text="follow up?", sender=MESSAGE_SENDER_USER)
    history = [
        Data(text="prev user", sender=MESSAGE_SENDER_USER),
        Data(text="prev ai", sender=MESSAGE_SENDER_AI),
    ]

    messages = build_initial_messages(input_value=msg, chat_history=history)

    assert len(messages) == 3
    assert isinstance(messages[0], HumanMessage)
    assert _content_text(messages[0]) == "prev user"
    assert isinstance(messages[1], AIMessage)
    assert _content_text(messages[1]) == "prev ai"
    assert isinstance(messages[2], HumanMessage)
    assert _content_text(messages[2]) == "follow up?"


def test_should_skip_data_items_with_empty_text_when_building_messages() -> None:
    msg = Message(text="hi", sender=MESSAGE_SENDER_USER)
    history = [
        Data(text="", sender=MESSAGE_SENDER_USER),
        Data(text="hello", sender=MESSAGE_SENDER_USER),
    ]

    messages = build_initial_messages(input_value=msg, chat_history=history)

    assert len(messages) == 2
    assert isinstance(messages[0], HumanMessage)
    assert _content_text(messages[0]) == "hello"
    assert isinstance(messages[1], HumanMessage)
    assert _content_text(messages[1]) == "hi"


def test_should_skip_data_items_with_whitespace_only_text() -> None:
    msg = Message(text="hi", sender=MESSAGE_SENDER_USER)
    history = [
        Data(text="   \n\t  ", sender=MESSAGE_SENDER_USER),
        Data(text="real content", sender=MESSAGE_SENDER_AI),
    ]

    messages = build_initial_messages(input_value=msg, chat_history=history)

    assert len(messages) == 2
    assert _content_text(messages[0]) == "real content"
    assert isinstance(messages[0], AIMessage)


def test_should_accept_single_data_object_as_chat_history() -> None:
    msg = Message(text="hi", sender=MESSAGE_SENDER_USER)
    single = Data(text="single history item", sender=MESSAGE_SENDER_USER)

    messages = build_initial_messages(input_value=msg, chat_history=single)

    assert len(messages) == 2
    assert _content_text(messages[0]) == "single history item"


def test_should_accept_list_of_messages_as_chat_history() -> None:
    msg = Message(text="hi", sender=MESSAGE_SENDER_USER)
    history = [
        Message(text="prev user msg", sender=MESSAGE_SENDER_USER),
        Message(text="prev ai msg", sender=MESSAGE_SENDER_AI),
    ]

    messages = build_initial_messages(input_value=msg, chat_history=history)

    assert len(messages) == 3
    assert isinstance(messages[0], HumanMessage)
    assert _content_text(messages[0]) == "prev user msg"
    assert isinstance(messages[1], AIMessage)
    assert _content_text(messages[1]) == "prev ai msg"


def test_should_accept_string_input_value() -> None:
    messages = build_initial_messages(input_value="plain string input", chat_history=None)

    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "plain string input"


def test_should_return_continue_message_when_input_is_empty_string() -> None:
    messages = build_initial_messages(input_value="", chat_history=None)

    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "Continue the conversation."


def test_should_return_continue_message_when_input_is_whitespace_only() -> None:
    messages = build_initial_messages(input_value="   \n\t   ", chat_history=None)

    assert len(messages) == 1
    assert messages[0].content == "Continue the conversation."


def test_should_return_continue_message_when_message_text_is_blank() -> None:
    msg = Message(text="   ", sender=MESSAGE_SENDER_USER)

    messages = build_initial_messages(input_value=msg, chat_history=None)

    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "Continue the conversation."


def test_should_return_continue_message_when_input_is_none_and_history_is_empty() -> None:
    messages = build_initial_messages(input_value=None, chat_history=None)

    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "Continue the conversation."


def test_should_preserve_multimodal_content_when_message_to_lc_returns_list() -> None:
    """Multimodal Messages produce list-content HumanMessages — helper must NOT flatten them.

    Regression: legacy code in agent.py extracted text and pushed images to chat_history
    (because AgentExecutor took `input: str`). create_agent accepts list content directly.
    """
    msg = Message(text="describe", sender=MESSAGE_SENDER_USER)
    multimodal_payload: list = [
        {"type": "text", "text": "describe"},
        {"type": "image_url", "image_url": {"url": "https://example.invalid/x.png"}},
    ]

    with patch.object(Message, "to_lc_message", return_value=HumanMessage(content=multimodal_payload)):
        messages = build_initial_messages(input_value=msg, chat_history=None)

    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[0].content, list)
    assert any(part.get("type") == "image_url" for part in messages[0].content)
    assert any(part.get("type") == "text" for part in messages[0].content)


def test_should_return_only_basemessage_instances() -> None:
    msg = Message(text="hi", sender=MESSAGE_SENDER_USER)
    history = [Data(text="prev", sender=MESSAGE_SENDER_USER)]

    messages = build_initial_messages(input_value=msg, chat_history=history)

    assert all(isinstance(m, BaseMessage) for m in messages)


def test_should_append_continue_message_when_input_blank_and_history_ends_with_ai_message() -> None:
    """Regression: empty input + history ending in AIMessage caused hallucinations.

    The LLM re-ran tool calls from earlier turns (observed in manual Smoke #5:
    agent re-emitted "17 x 23 = 391" + Wikipedia title from a much earlier turn
    when the user submitted an empty message).

    The safeguard must always inject a HumanMessage when the user provided no
    fresh input - regardless of what the history's tail looks like - so the LLM
    is never asked to "continue" from a state ending in AIMessage.
    """
    history = [
        Data(text="Calculate 17 * 23", sender=MESSAGE_SENDER_USER),
        Data(text="17 * 23 = 391", sender=MESSAGE_SENDER_AI),
        Data(text="What is my favorite color?", sender=MESSAGE_SENDER_USER),
        Data(text="Your favorite color is purple.", sender=MESSAGE_SENDER_AI),
    ]

    messages = build_initial_messages(input_value="", chat_history=history)

    assert isinstance(messages[-1], HumanMessage)
    assert _content_text(messages[-1]) == "Continue the conversation."


def test_should_append_continue_message_when_input_is_none_and_history_ends_with_ai_message() -> None:
    history = [
        Data(text="hello", sender=MESSAGE_SENDER_USER),
        Data(text="hi there", sender=MESSAGE_SENDER_AI),
    ]

    messages = build_initial_messages(input_value=None, chat_history=history)

    assert isinstance(messages[-1], HumanMessage)
    assert _content_text(messages[-1]) == "Continue the conversation."


def test_should_append_continue_message_when_input_is_blank_message_and_history_ends_with_ai_message() -> None:
    blank_input = Message(text="   ", sender=MESSAGE_SENDER_USER)
    history = [
        Data(text="prior question", sender=MESSAGE_SENDER_USER),
        Data(text="prior answer", sender=MESSAGE_SENDER_AI),
    ]

    messages = build_initial_messages(input_value=blank_input, chat_history=history)

    assert isinstance(messages[-1], HumanMessage)
    assert _content_text(messages[-1]) == "Continue the conversation."


def test_should_not_double_inject_continue_message_when_history_already_ends_with_human_message() -> None:
    """Inject exactly one continuation when input is blank and history ends with a HumanMessage.

    Regression guard: when input is blank and history happens to end with a HumanMessage
    (rare - usually only when the LLM call failed previously), still inject exactly ONE
    continuation, not two.
    """
    history = [
        Data(text="lonely user question", sender=MESSAGE_SENDER_USER),
    ]

    messages = build_initial_messages(input_value="", chat_history=history)

    assert messages.count(HumanMessage(content="Continue the conversation.")) <= 1
    assert isinstance(messages[-1], HumanMessage)
    # The safeguard ensures a fresh prompt — the original HumanMessage may stay or be replaced,
    # but the LAST message must be the continuation prompt.
    assert _content_text(messages[-1]) == "Continue the conversation."
