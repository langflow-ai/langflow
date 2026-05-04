"""Build the initial `messages` list passed to `langchain.agents.create_agent` graphs.

`create_agent` expects `{"messages": [BaseMessage, ...]}` as input — unlike the legacy
`AgentExecutor`, which took `{"input": str, "chat_history": [...]}`. This helper performs
the conversion and applies a safety guard so empty/whitespace input does not reach
providers (Anthropic in particular) that reject empty content.
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
    """Convert (input_value, chat_history) into the messages list expected by create_agent.

    - Skips chat-history items whose `.text` is empty/whitespace (some providers reject them).
    - Preserves multimodal content untouched (image/audio parts inside `to_lc_message()`).
    - Falls back to a "Continue the conversation." HumanMessage when the resulting list
      is empty or its last message has blank content.
    """
    messages: list[BaseMessage] = []

    if chat_history is not None:
        history_items = _normalize_history(chat_history)
        for item in history_items:
            if _has_blank_text(item):
                continue
            messages.append(item.to_lc_message())

    appended_input = _append_input(messages, input_value)

    # If the user provided no fresh input this turn, ensure the message list ends with
    # a HumanMessage prompting continuation. Without this, the LLM sees a state ending
    # in AIMessage (or in a blank human turn) and may hallucinate by re-running tool
    # calls from earlier turns — observed in manual Smoke #5 (empty submit replayed
    # the calculator + URL fetch from a much earlier turn).
    if not appended_input:
        messages.append(HumanMessage(content=CONTINUE_MESSAGE))

    return messages


def _normalize_history(
    chat_history: list[Data] | list[Message] | Data | Iterable[Data | Message],
) -> list[Data | Message]:
    if isinstance(chat_history, (Data, Message)):
        return [chat_history]
    return list(chat_history)


def _has_blank_text(item: Data | Message) -> bool:
    text = getattr(item, "text", None)
    return isinstance(text, str) and not text.strip()


def _append_input(messages: list[BaseMessage], input_value: Message | str | None) -> bool:
    """Append the user input. Returns True if a non-blank message was appended."""
    if isinstance(input_value, Message):
        if _has_blank_text(input_value):
            return False
        messages.append(input_value.to_lc_message())
        return True
    if isinstance(input_value, str):
        if not input_value.strip():
            return False
        messages.append(HumanMessage(content=input_value))
        return True
    return False


