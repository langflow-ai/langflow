"""Build the initial `messages` list passed to `langchain.agents.create_agent` graphs.

`create_agent` (LangGraph) expects `{"messages": [BaseMessage, ...]}` as input — unlike
the legacy `AgentExecutor`, which took `{"input": str, "chat_history": [...]}`. This
helper performs the conversion.
"""

from collections.abc import Iterable

from langchain_core.messages import BaseMessage, HumanMessage

from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.message import Message

CONTINUE_MESSAGE = "Continue the conversation."


def build_initial_messages(
    *,
    input_value: Message | str | None,
    chat_history: list[Data] | list[Message] | Data | Iterable[Data | Message] | None,
) -> list[BaseMessage]:
    """Convert (input_value, chat_history) into the messages list expected by create_agent."""
    messages: list[BaseMessage] = []

    if chat_history is not None:
        for item in _normalize_history(chat_history):
            # Mirror the current-turn guard in `_append_input`: a blank-text item is
            # only truly empty when it ALSO has no files. An image-only message from a
            # prior turn (text="", files=[image]) must survive — dropping it silently
            # loses multimodal context on the next turn.
            if _has_blank_text(item) and not getattr(item, "files", None):
                continue
            converted = _safe_to_lc_message(item)
            if converted is not None:
                messages.append(converted)

    if not _append_input(messages, input_value):
        # No fresh user input this turn. Always inject a deterministic continuation
        # prompt — never let blank content reach the provider, and never let the LLM
        # see a tail-AIMessage with no fresh user turn (causes silent re-execution
        # of earlier tool calls).
        messages.append(HumanMessage(content=CONTINUE_MESSAGE))

    return messages


def _has_blank_text(item: Data | Message) -> bool:
    text = getattr(item, "text", None)
    return isinstance(text, str) and not text.strip()


def _normalize_history(
    chat_history: list[Data] | list[Message] | Data | Iterable[Data | Message],
) -> list[Data | Message]:
    if isinstance(chat_history, (Data, Message)):
        return [chat_history]
    return list(chat_history)


def _append_input(messages: list[BaseMessage], input_value: Message | str | None) -> bool:
    """Append the user input. Returns True iff a non-blank message was appended.

    A Message with blank text is still appended when files are attached — the file
    payload IS the input. `Message.to_lc_message()` builds the multimodal HumanMessage
    correctly in that case.
    """
    if isinstance(input_value, Message):
        if _has_blank_text(input_value) and not getattr(input_value, "files", None):
            return False
        messages.append(input_value.to_lc_message())
        return True
    if isinstance(input_value, str):
        if not input_value.strip():
            return False
        messages.append(HumanMessage(content=input_value))
        return True
    return False


def _safe_to_lc_message(item: Data | Message) -> BaseMessage | None:
    """Convert a chat_history item to a BaseMessage, or skip+log when malformed.

    `Data.to_lc_message()` raises `ValueError` if the underlying dict is missing the
    required `text` / `sender` keys. Without this guard a single malformed item would
    crash the whole turn — the legacy AgentExecutor path silently dropped the entire
    chat_history under similar circumstances, so we preserve that "noisy log, keep
    going" contract instead of regressing to a hard failure. Catch is narrowed to
    `ValueError` so genuine bugs in `to_lc_message` implementations still surface.
    """
    try:
        return item.to_lc_message()
    except ValueError as exc:
        logger.warning(f"Skipping malformed chat_history item ({type(item).__name__}): {exc}")
        return None
