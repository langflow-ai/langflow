"""The message rows an agent loop flow passes between its components, and where it finds the harness runtime.

A loop state is a DataFrame with one row per LangChain message. A row shows `text` and `sender` and keeps the whole
message in `lc_message` (tool calls, tool call ids, usage), so every edge carries the real history and nothing is
rebuilt from text. A row without `lc_message` is read as a message record (`type` and `data`, the table Agent Context
and context flows use) or else as a chat row, from its text and sender.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    message_to_dict,
    messages_from_dict,
)

if TYPE_CHECKING:
    from lfx.schema.dataframe import DataFrame

# The graph context key of the HarnessLoopRuntime whose builder owns the run: its middleware, its scopes, its display.
HARNESS_LOOP_KEY = "harness_loop"
LC_MESSAGE = "lc_message"
_SENDERS = {HumanMessage: "User", AIMessage: "Machine", SystemMessage: "System", ToolMessage: "Tool"}


def messages_to_rows(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    return [
        {"text": message.text, "sender": _SENDERS.get(type(message), "User"), LC_MESSAGE: message_to_dict(message)}
        for message in messages
    ]


def row_to_message(row: dict[str, Any]) -> BaseMessage:
    record = row.get(LC_MESSAGE)
    if not isinstance(record, dict) and isinstance(row.get("data"), dict):
        record = {"type": row.get("type"), "data": row["data"]}
    if isinstance(record, dict):
        return messages_from_dict([record])[0]
    text = row.get("text")
    text = "" if text is None or (isinstance(text, float) and math.isnan(text)) else str(text)
    sender = row.get("sender")
    if sender in {"Machine", "AI"}:
        return AIMessage(content=text)
    if sender == "System":
        return SystemMessage(content=text)
    return HumanMessage(content=text)


def rows_to_messages(rows: DataFrame) -> list[BaseMessage]:
    return [row_to_message(row) for row in rows.to_dict(orient="records")]


def is_answer(message: BaseMessage) -> bool:
    """The model is done: an AI message that asks for no tools."""
    return isinstance(message, AIMessage) and not message.tool_calls
