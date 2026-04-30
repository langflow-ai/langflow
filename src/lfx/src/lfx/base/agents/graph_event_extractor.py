"""Extract the final assistant text from a LangGraph agent state.

`langchain.agents.create_agent` returns a `CompiledStateGraph`. Its `on_chain_end` event
emits `data.output = {"messages": [HumanMessage, ..., AIMessage]}` (a state dict),
not the legacy `AgentFinish.return_values["output"]` shape.
"""

from typing import Any

from langchain_core.messages import AIMessage


def extract_final_text(state: Any) -> str:
    """Return the textual content of the last `AIMessage` in `state.messages`.

    Returns an empty string if the state is None, has no messages, or the last
    AIMessage has no text parts (e.g. it only emitted tool calls).
    """
    messages = _get_messages(state)
    if not messages:
        return ""

    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return _extract_text_from_content(message.content)
    return ""


def _get_messages(state: Any) -> list:
    if state is None:
        return []
    if isinstance(state, dict):
        messages = state.get("messages")
        return list(messages) if messages else []
    messages = getattr(state, "messages", None)
    return list(messages) if messages else []


def _extract_text_from_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(_text_part(part) for part in content)
    return ""


def _text_part(part: object) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, dict) and part.get("type") == "text":
        text = part.get("text")
        return text if isinstance(text, str) else ""
    return ""
