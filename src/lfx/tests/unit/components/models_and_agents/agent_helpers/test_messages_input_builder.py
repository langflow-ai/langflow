"""Tests for build_initial_messages — converts (input_value, chat_history) → list[BaseMessage].

This helper lives PRIVATE to AgentComponent (`models_and_agents/agent_helpers/`) per the
"AgentComponent-only migration" plan (CZL/PLAN_agent_create_agent_only.md). It must NOT be
imported by other components — if a second consumer ever appears, move it up to base/.
"""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from lfx.components.models_and_agents.agent_helpers.messages_input_builder import (
    build_initial_messages,
)
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


def test_should_build_human_message_with_input_text_when_no_history() -> None:
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


def test_should_skip_history_items_with_blank_text() -> None:
    """Anthropic and some other providers reject empty content blocks; drop them upstream."""
    msg = Message(text="hi", sender=MESSAGE_SENDER_USER)
    history = [
        Data(text="", sender=MESSAGE_SENDER_USER),
        Data(text="   \n\t  ", sender=MESSAGE_SENDER_AI),
        Data(text="real content", sender=MESSAGE_SENDER_USER),
    ]

    messages = build_initial_messages(input_value=msg, chat_history=history)

    assert len(messages) == 2
    assert _content_text(messages[0]) == "real content"
    assert isinstance(messages[0], HumanMessage)
    assert _content_text(messages[1]) == "hi"


def test_should_emit_continue_message_when_input_is_none_and_history_is_empty() -> None:
    """Empty/None input must produce a deterministic prompt — never let blank reach the LLM.

    Why: Anthropic API rejects empty content blocks. More subtly, an empty submit with a
    history ending in AIMessage causes the model to "continue" — observed in manual smoke
    tests as the agent silently re-running tool calls from an earlier turn.
    """
    messages = build_initial_messages(input_value=None, chat_history=None)

    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "Continue the conversation."


def test_should_emit_continue_message_when_input_is_empty_string() -> None:
    messages = build_initial_messages(input_value="", chat_history=None)

    assert len(messages) == 1
    assert messages[0].content == "Continue the conversation."


def test_should_emit_continue_message_when_input_is_whitespace_only() -> None:
    messages = build_initial_messages(input_value="   \n\t   ", chat_history=None)

    assert len(messages) == 1
    assert messages[0].content == "Continue the conversation."


def test_should_emit_continue_message_when_input_message_text_is_blank() -> None:
    msg = Message(text="   ", sender=MESSAGE_SENDER_USER)

    messages = build_initial_messages(input_value=msg, chat_history=None)

    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "Continue the conversation."


def test_should_preserve_input_message_when_text_is_blank_but_files_are_attached() -> None:
    """Image-only submissions must reach the agent — the file payload is the input.

    Bug Gabriel flagged on PR #12982 (line 71 of the original messages_input_builder):
    `Message(text="", files=[image])` was treated as blank, the multimodal payload was
    dropped, and the agent saw "Continue the conversation." instead of the image.

    The check must consider files in addition to text. `Message.to_lc_message()` already
    builds a multimodal HumanMessage when text is empty but files are present.
    """
    from unittest.mock import patch

    msg = Message(text="", sender=MESSAGE_SENDER_USER, files=["/tmp/x.png"])
    multimodal_payload: list = [
        {"type": "text", "text": ""},
        {"type": "image_url", "image_url": {"url": "https://example.invalid/x.png"}},
    ]

    # Patch to_lc_message so we don't touch the filesystem; the contract under test is
    # "build_initial_messages calls to_lc_message and uses its result", not how
    # Message.to_lc_message handles file paths.
    with patch.object(Message, "to_lc_message", return_value=HumanMessage(content=multimodal_payload)):
        messages = build_initial_messages(input_value=msg, chat_history=None)

    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[0].content, list), (
        "must keep the multimodal list payload, not collapse to a Continue.. fallback"
    )
    assert any(part.get("type") == "image_url" for part in messages[0].content)


def test_should_emit_continue_message_when_input_text_is_blank_and_files_is_empty() -> None:
    """Regression guard for S5: do NOT promote a fully blank Message just because files exists.

    Only attached files should keep the message alive. An empty files list (or None)
    must still trigger the Continue.. fallback.
    """
    msg = Message(text="   ", sender=MESSAGE_SENDER_USER, files=[])

    messages = build_initial_messages(input_value=msg, chat_history=None)

    assert len(messages) == 1
    assert messages[0].content == "Continue the conversation."


def test_should_inject_continue_message_when_input_is_blank_and_history_ends_with_ai_message() -> None:
    """T2 regression guard: the LLM must never see a tail-AIMessage with no fresh user turn.

    Manual Smoke #5 caught this: the agent re-executed the calculator and URL-fetch tool
    calls from a much earlier turn when the user submitted an empty message. The fix is
    to ALWAYS append a fresh continuation prompt when no user input is given this turn.
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
    # And the history is preserved before the safeguard.
    assert len(messages) == 5
    assert _content_text(messages[0]) == "Calculate 17 * 23"


def test_should_skip_malformed_chat_history_items_without_crashing_the_turn() -> None:
    """Malformed `Data` entries in chat_history are skipped, not fatal.

    `Data.to_lc_message()` raises `ValueError` if the underlying dict is missing
    the required `text` / `sender` keys. The legacy `AgentExecutor` path silently
    dropped the entire chat_history when any item failed validation; we preserve
    a similar "log and keep going" contract instead of letting one bad item
    crash the whole turn. Well-formed neighbors must still come through.
    """
    history = [
        Data(text="hello", sender=MESSAGE_SENDER_USER),  # well-formed
        Data(data={"text": "no sender"}),  # malformed: missing sender
        Data(data={"sender": MESSAGE_SENDER_AI}),  # malformed: missing text
        Data(text="goodbye", sender=MESSAGE_SENDER_AI),  # well-formed
    ]

    messages = build_initial_messages(input_value="ping", chat_history=history)

    # Only the two well-formed Data items + the user input message survive.
    assert len(messages) == 3
    assert _content_text(messages[0]) == "hello"
    assert _content_text(messages[1]) == "goodbye"
    assert isinstance(messages[2], HumanMessage)
    assert _content_text(messages[2]) == "ping"
