"""Lossless message tables for custom context flows."""

from copy import deepcopy

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage, messages_from_dict, messages_to_dict

from lfx.schema.dataframe import DataFrame


def messages_to_table(messages: list[BaseMessage]) -> DataFrame:
    """Keep rich content, tool calls, IDs, and metadata in each row's data object."""
    return DataFrame(deepcopy(messages_to_dict(messages)), columns=["type", "data"])


def messages_from_rows(rows: list[dict]) -> list[BaseMessage]:
    if not isinstance(rows, list) or any(
        not isinstance(row, dict)
        or row.get("type") not in {"human", "ai", "system", "tool", "function", "chat"}
        or not isinstance(row.get("data"), dict)
        for row in rows
    ):
        msg = "Context messages need type and data columns containing complete message records."
        raise ValueError(msg)
    messages = messages_from_dict(deepcopy(rows))
    pending: set[str] = set()
    for message in messages:
        if isinstance(message, ToolMessage):
            if message.tool_call_id not in pending:
                msg = "Each context tool result must match one preceding tool call."
                raise ValueError(msg)
            pending.remove(message.tool_call_id)
        else:
            if pending:
                msg = "Context flows must keep tool calls and their results together."
                raise ValueError(msg)
            if isinstance(message, AIMessage):
                ids = [call.get("id") for call in message.tool_calls]
                if any(not isinstance(call_id, str) or not call_id for call_id in ids) or len(set(ids)) != len(ids):
                    msg = "Context tool calls need distinct non-empty IDs."
                    raise ValueError(msg)
                pending = set(ids)
    if pending:
        msg = "Context flows must keep tool calls and their results together."
        raise ValueError(msg)
    return messages


def messages_from_table(table: DataFrame) -> list[BaseMessage]:
    if not isinstance(table, DataFrame):
        msg = "A context flow must return a message Table, not a display artifact."
        raise TypeError(msg)
    if not {"type", "data"} <= set(table.columns):
        msg = "Context messages need type and data columns containing complete message records."
        raise ValueError(msg)
    return messages_from_rows(table[["type", "data"]].to_dict(orient="records"))
