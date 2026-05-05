"""Build the initial `messages` list passed to `langchain.agents.create_agent` graphs.

`create_agent` (LangGraph) expects `{"messages": [BaseMessage, ...]}` as input — unlike
the legacy `AgentExecutor`, which took `{"input": str, "chat_history": [...]}`. This
helper performs the conversion.
"""

from collections.abc import Iterable

from langchain_core.messages import BaseMessage, HumanMessage

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
            if _has_blank_text(item):
                continue
            messages.append(item.to_lc_message())

    if not _append_input(messages, input_value):
        # No fresh user input this turn. Always inject a deterministic continuation
        # prompt — never let blank content reach the provider, and never let the LLM
        # see a tail-AIMessage with no fresh user turn (causes silent re-execution
        # of earlier tool calls; observed in manual Smoke #5).
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
