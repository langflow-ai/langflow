"""Utilities for executing tools in agent workflows.

This module provides functions for:
- Executing tools (sync and async)
- Building tool result DataFrames
- Formatting tool results
"""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any


async def execute_tool(tool: Any, args: dict[str, Any]) -> Any:
    """Execute a tool, handling both sync and async tools.

    Supports multiple tool interfaces:
    - LangChain tools (ainvoke, arun, invoke, run)
    - Callable functions (sync and async)

    Args:
        tool: The tool to execute
        args: Arguments to pass to the tool

    Returns:
        The tool execution result

    Raises:
        TypeError: If the tool is not executable
    """
    # Check if tool has ainvoke (LangChain tools)
    if hasattr(tool, "ainvoke"):
        return await tool.ainvoke(args)

    # Check if tool has arun
    if hasattr(tool, "arun"):
        return await tool.arun(**args)

    # Check if tool has invoke
    if hasattr(tool, "invoke"):
        return tool.invoke(args)

    # Check if tool has run
    if hasattr(tool, "run"):
        return tool.run(**args)

    # Check if tool is callable
    if callable(tool):
        if inspect.iscoroutinefunction(tool):
            return await tool(**args)
        # Run sync callable in executor
        return await asyncio.to_thread(tool, **args)

    msg = f"Tool {tool} is not executable"
    raise TypeError(msg)


def format_tool_result(result: Any) -> str:
    """Format a tool result as a string.

    Args:
        result: The tool execution result

    Returns:
        String representation of the result
    """
    if isinstance(result, str):
        return result
    if isinstance(result, dict | list):
        return json.dumps(result, indent=2)
    return str(result)


def build_tool_result_row(
    tool_name: str,
    tool_call_id: str,
    result: Any | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build a tool result row for a DataFrame.

    Args:
        tool_name: Name of the tool
        tool_call_id: ID of the tool call
        result: Tool execution result (if successful)
        error: Error message (if failed)

    Returns:
        Dictionary representing a tool result row
    """
    content = f"Error: {error}" if error else format_tool_result(result)

    return {
        "text": content,
        "sender": "Tool",
        "sender_name": tool_name,
        "tool_calls": None,
        "has_tool_calls": False,
        "tool_call_id": tool_call_id,
        "is_tool_result": True,
    }


def build_ai_message_row(
    text: str,
    tool_calls: list[dict[str, Any]],
    message_id: str | None = None,
    content_blocks: list[Any] | None = None,
) -> dict[str, Any]:
    """Build an AI message row for a DataFrame.

    Args:
        text: The AI message text
        tool_calls: List of tool calls from the AI message
        message_id: Optional message ID to pass through the loop
        content_blocks: Optional content blocks to preserve through the loop

    Returns:
        Dictionary representing an AI message row
    """
    return {
        "text": text,
        "sender": "Machine",
        "sender_name": "AI",
        "tool_calls": tool_calls,
        "has_tool_calls": True,
        "tool_call_id": None,
        "is_tool_result": False,
        "_agent_message_id": message_id,
        "_agent_content_blocks": content_blocks,
    }


def extract_tool_call_info(tc: Any) -> tuple[str, dict[str, Any], str]:
    """Extract name, args, and id from a tool call.

    Handles both dict and object formats.

    Args:
        tc: Tool call (dict or object)

    Returns:
        Tuple of (name, args, id)
    """
    if isinstance(tc, dict):
        return (
            tc.get("name", ""),
            tc.get("args", {}),
            tc.get("id", ""),
        )
    return (
        getattr(tc, "name", ""),
        getattr(tc, "args", {}),
        getattr(tc, "id", ""),
    )


def build_tools_by_name(tools: list[Any]) -> dict[str, Any]:
    """Build a dictionary mapping tool names to tools.

    Args:
        tools: List of tools

    Returns:
        Dictionary mapping tool names to tool objects
    """
    return {getattr(t, "name", ""): t for t in tools}


async def execute_tool_calls(
    tool_calls: list[Any],
    tools: list[Any],
    ai_message_text: str = "",
    ai_message_id: str | None = None,
) -> list[dict[str, Any]]:
    """Execute all tool calls and return message rows.

    This is the main entry point for tool execution. It:
    1. Creates an AI message row with the tool calls
    2. Executes each tool call
    3. Creates tool result rows for each execution

    Args:
        tool_calls: List of tool calls to execute
        tools: List of available tools
        ai_message_text: Text content of the AI message
        ai_message_id: Optional message ID to pass through

    Returns:
        List of message row dictionaries (AI message + tool results)
    """
    message_rows: list[dict[str, Any]] = []

    if not tool_calls:
        return message_rows

    # Add the AI message row
    message_rows.append(build_ai_message_row(ai_message_text, tool_calls, ai_message_id))

    # Build tools lookup
    tools_by_name = build_tools_by_name(tools)

    # Execute each tool call
    for tc in tool_calls:
        tool_name, tool_args, tool_call_id = extract_tool_call_info(tc)

        if not tool_name:
            message_rows.append(
                build_tool_result_row(
                    tool_name="unknown",
                    tool_call_id=tool_call_id,
                    error="Tool call missing name",
                )
            )
            continue

        tool = tools_by_name.get(tool_name)
        if tool is None:
            message_rows.append(
                build_tool_result_row(
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    error=f"Tool '{tool_name}' not found",
                )
            )
            continue

        try:
            result = await execute_tool(tool, tool_args)
            message_rows.append(
                build_tool_result_row(
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    result=result,
                )
            )
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
            message_rows.append(
                build_tool_result_row(
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    error=str(e),
                )
            )

    return message_rows
