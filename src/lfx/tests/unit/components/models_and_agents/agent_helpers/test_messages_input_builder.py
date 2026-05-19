"""Tests for build_initial_messages — converts (input_value, chat_history) → list[BaseMessage].

This helper lives PRIVATE to AgentComponent (`models_and_agents/agent_helpers/`) per the
"AgentComponent-only migration" plan (CZL/PLAN_agent_create_agent_only.md). It must NOT be
imported by other components — if a second consumer ever appears, move it up to base/.
"""

import pytest
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


def test_should_preserve_history_message_when_text_is_blank_but_files_are_attached() -> None:
    """An image-only message from a PRIOR turn must survive into the next turn's context.

    Bug Gabriel flagged on PR #12992 (discussion r3259225755): the history loop skipped
    any item with blank text via `_has_blank_text`, ignoring attached files. A saved
    `Message(text="", files=[image])` (image-only upload from an earlier turn) was
    therefore dropped, so the image silently disappeared from context on the next turn.
    `_append_input` already guards this for the current turn (line 66); the history loop
    must apply the same files-aware guard.
    """
    from unittest.mock import patch

    history_image = Message(text="", sender=MESSAGE_SENDER_USER, files=["/tmp/prev.png"])
    multimodal_payload: list = [
        {"type": "text", "text": ""},
        {"type": "image_url", "image_url": {"url": "https://example.invalid/prev.png"}},
    ]
    follow_up = Message(text="what is in that image?", sender=MESSAGE_SENDER_USER)

    # Patch to_lc_message so we don't touch the filesystem; the contract under test is
    # "the history loop keeps a blank-text item when files are attached", not how
    # Message.to_lc_message resolves file paths.
    with patch.object(Message, "to_lc_message", return_value=HumanMessage(content=multimodal_payload)):
        messages = build_initial_messages(input_value=follow_up, chat_history=[history_image])

    assert len(messages) == 2, "the image-only history message must NOT be skipped"
    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[0].content, list), "must keep the multimodal list payload from the history image message"
    assert any(part.get("type") == "image_url" for part in messages[0].content)


def test_should_skip_history_message_when_text_is_blank_and_files_is_empty() -> None:
    """Symmetry with the current-turn guard: only ATTACHED files keep a blank item alive.

    A history `Message` with blank text and an empty files list must still be skipped —
    the files-aware guard must not promote a fully blank message just because the
    `files` attribute exists.
    """
    history = [
        Message(text="", sender=MESSAGE_SENDER_USER, files=[]),
        Message(text="real history", sender=MESSAGE_SENDER_AI),
    ]
    msg = Message(text="hi", sender=MESSAGE_SENDER_USER)

    messages = build_initial_messages(input_value=msg, chat_history=history)

    assert len(messages) == 2, "blank text + empty files history item must still be skipped"
    assert _content_text(messages[0]) == "real history"
    assert _content_text(messages[1]) == "hi"


def test_should_emit_continue_message_when_input_is_none_and_history_is_empty() -> None:
    """Empty/None input must produce a deterministic prompt — never let blank reach the LLM.

    Why: Anthropic API rejects empty content blocks. More subtly, an empty submit with a
    history ending in AIMessage causes the model to "continue" — re-running tool calls
    from an earlier turn.
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
    """Do NOT promote a fully blank Message just because `files` exists.

    Only attached files should keep the message alive. An empty files list (or None)
    must still trigger the Continue.. fallback.
    """
    msg = Message(text="   ", sender=MESSAGE_SENDER_USER, files=[])

    messages = build_initial_messages(input_value=msg, chat_history=None)

    assert len(messages) == 1
    assert messages[0].content == "Continue the conversation."


def test_should_inject_continue_message_when_input_is_blank_and_history_ends_with_ai_message() -> None:
    """The LLM must never see a tail-AIMessage with no fresh user turn.

    Without this guard, an empty submit on top of a history ending in AIMessage causes
    the agent to silently re-execute tool calls from an earlier turn. Always append a
    fresh continuation prompt when no user input is given this turn.
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


def test_should_propagate_non_value_error_from_to_lc_message() -> None:
    """Non-ValueError exceptions from `to_lc_message()` must propagate, not be swallowed.

    Only `ValueError` is a "malformed entry, skip it" signal. Genuine bugs in
    `to_lc_message()` (e.g., `KeyError` from a typo, `AttributeError` from a None
    deref) MUST surface — otherwise the safety net hides regressions in the
    Data/Message conversion code itself.
    """
    from unittest.mock import patch

    history = [Data(text="ok", sender=MESSAGE_SENDER_USER)]
    with patch.object(Data, "to_lc_message", side_effect=KeyError("missing-key")), pytest.raises(KeyError):
        build_initial_messages(input_value="ping", chat_history=history)


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
