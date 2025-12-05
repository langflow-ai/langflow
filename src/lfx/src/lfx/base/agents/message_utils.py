"""Utilities for converting messages between Langflow and LangChain formats.

This module provides functions for:
- Converting Langflow Messages/DataFrames to LangChain BaseMessages
- Extracting message metadata (tool_calls, message IDs) from DataFrames
- Sanitizing tool_calls for API compatibility
"""

from __future__ import annotations

import math
import uuid
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

if TYPE_CHECKING:
    from lfx.schema.dataframe import DataFrame
    from lfx.schema.message import Message


def sanitize_tool_calls(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sanitize tool_calls to ensure all have valid IDs and names.

    This filters out incomplete tool_calls that may come from streaming aggregation
    and ensures all tool_calls have the required fields for the OpenAI API.

    Args:
        tool_calls: List of tool call dictionaries

    Returns:
        List of sanitized tool calls with valid names and IDs
    """
    sanitized = []
    for tc in tool_calls:
        tc_copy = dict(tc) if isinstance(tc, dict) else tc
        if isinstance(tc_copy, dict):
            # Skip tool_calls with empty or missing name
            tc_name = tc_copy.get("name", "")
            if not tc_name:
                continue
            # Ensure valid ID
            if tc_copy.get("id") is None or tc_copy.get("id") == "":
                tc_copy["id"] = f"call_{uuid.uuid4().hex[:24]}"
        sanitized.append(tc_copy)
    return sanitized


def extract_message_id_from_dataframe(df: DataFrame) -> str | None:
    """Extract the agent message ID from a DataFrame if present.

    This looks for the _agent_message_id field that ExecuteTool adds
    to pass the message ID through the loop back to CallModel.

    Args:
        df: DataFrame containing message history

    Returns:
        The message ID if found, None otherwise
    """
    for _, row in df.iterrows():
        msg_id = row.get("_agent_message_id")
        # Check if it's a valid ID (not None and not NaN)
        if msg_id is not None:
            is_nan = isinstance(msg_id, float) and math.isnan(msg_id)
            if not is_nan:
                return msg_id
    return None


def extract_content_blocks_from_dataframe(df: DataFrame) -> list[Any] | None:
    """Extract the agent content blocks from a DataFrame if present.

    This looks for the _agent_content_blocks field that ExecuteTool adds
    to pass the content_blocks through the loop back to CallModel.
    This preserves the "Agent Steps" content blocks showing tool executions.

    Args:
        df: DataFrame containing message history

    Returns:
        The content blocks if found, None otherwise
    """
    for _, row in df.iterrows():
        content_blocks = row.get("_agent_content_blocks")
        # Check if it's valid (not None and not NaN)
        if content_blocks is not None:
            is_nan = isinstance(content_blocks, float) and math.isnan(content_blocks)
            if not is_nan:
                return content_blocks
    return None


def dataframe_to_lc_messages(df: DataFrame) -> list[BaseMessage]:
    """Convert a DataFrame of messages to LangChain BaseMessages.

    Handles:
    - User messages -> HumanMessage
    - AI/Machine messages -> AIMessage (with optional tool_calls)
    - System messages -> SystemMessage
    - Tool result messages -> ToolMessage

    Args:
        df: DataFrame with columns: text, sender, tool_calls, tool_call_id, is_tool_result

    Returns:
        List of LangChain BaseMessage objects
    """
    lc_messages: list[BaseMessage] = []

    for _, row in df.iterrows():
        sender = row.get("sender", "User")
        text = row.get("text", "")
        is_tool_result = row.get("is_tool_result")
        tool_call_id = row.get("tool_call_id", "")
        tool_calls = row.get("tool_calls")

        # Check explicitly for True (nan from DataFrame is truthy but not True)
        if is_tool_result is True:
            # Tool result message
            lc_messages.append(ToolMessage(content=text, tool_call_id=tool_call_id or ""))
        elif sender == "Machine":
            # AI message - may have tool_calls
            ai_msg = AIMessage(content=text)
            # Check for valid tool_calls (not None and not NaN from DataFrame)
            is_nan = isinstance(tool_calls, float) and math.isnan(tool_calls)
            if tool_calls is not None and not is_nan:
                sanitized = sanitize_tool_calls(tool_calls)
                if sanitized:
                    ai_msg.tool_calls = sanitized
            lc_messages.append(ai_msg)
        elif sender == "System":
            lc_messages.append(SystemMessage(content=text))
        else:
            # User or unknown -> HumanMessage
            lc_messages.append(HumanMessage(content=text))

    return lc_messages


def messages_to_lc_messages(messages: list[Message]) -> list[BaseMessage]:
    """Convert a list of Langflow Messages to LangChain BaseMessages.

    Args:
        messages: List of Langflow Message objects

    Returns:
        List of LangChain BaseMessage objects
    """
    lc_messages: list[BaseMessage] = []

    for msg in messages:
        # Handle string inputs (e.g., from ChatInput)
        if isinstance(msg, str):
            lc_messages.append(HumanMessage(content=msg))
            continue

        is_tool_result = msg.data.get("is_tool_result", False) if msg.data else False
        tool_call_id = msg.data.get("tool_call_id", "") if msg.data else ""
        tool_calls = msg.data.get("tool_calls") if msg.data else None

        if is_tool_result:
            lc_messages.append(ToolMessage(content=msg.text or "", tool_call_id=tool_call_id or ""))
        elif msg.sender == "Machine":
            ai_msg = AIMessage(content=msg.text or "")
            if tool_calls:
                sanitized = sanitize_tool_calls(tool_calls)
                if sanitized:
                    ai_msg.tool_calls = sanitized
            lc_messages.append(ai_msg)
        elif msg.sender == "System":
            lc_messages.append(SystemMessage(content=msg.text or ""))
        else:
            # User or unknown -> HumanMessage
            lc_messages.append(HumanMessage(content=msg.text or ""))

    return lc_messages


def convert_to_lc_messages(
    messages: list[Message] | DataFrame,
) -> list[BaseMessage]:
    """Convert Langflow Messages or DataFrame to LangChain BaseMessages.

    This is the main entry point for message conversion. It automatically
    detects the input type and delegates to the appropriate converter.

    Args:
        messages: Either a list of Message objects or a DataFrame

    Returns:
        List of LangChain BaseMessage objects
    """
    # Import here to avoid circular imports
    from lfx.schema.dataframe import DataFrame

    if isinstance(messages, DataFrame):
        return dataframe_to_lc_messages(messages)
    return messages_to_lc_messages(messages)
