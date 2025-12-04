"""ExecuteTool component - executes tool calls from an AI message.

This component takes an AI message with tool_calls and the available tools,
executes them, and returns the AI message plus tool results as a DataFrame.
The WhileLoop handles accumulating these with the existing conversation history.
"""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import HandleInput, MessageInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class ExecuteToolComponent(Component):
    """Executes tool calls and returns AI message + tool results.

    This component:
    1. Takes an AI message containing tool_calls (from CallModel)
    2. Finds matching tools from the provided tools list
    3. Executes all tools with their arguments
    4. Returns a DataFrame with the AI message and tool results

    The output connects back to WhileLoop, which accumulates these
    messages with the existing conversation history.
    """

    display_name = "Execute Tool"
    description = "Execute tool calls and return AI message with tool results."
    icon = "play"
    category = "agent_blocks"

    inputs = [
        MessageInput(
            name="ai_message",
            display_name="AI Message",
            info="The AI message containing tool_calls to execute (from CallModel).",
            required=True,
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            info="The available tools to execute.",
            input_types=["Tool"],
            is_list=True,
            required=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Messages",
            name="messages",
            method="execute_tools",
        ),
    ]

    async def execute_tools(self) -> DataFrame:
        """Execute all tool calls and return AI message + tool results."""
        # Build message rows for just the new messages (AI + tool results)
        message_rows: list[dict] = []

        # Get tool_calls from AI message
        raw_tool_calls = []
        ai_message_text = ""
        if self.ai_message is not None:
            if hasattr(self.ai_message, "data") and self.ai_message.data:
                raw_tool_calls = self.ai_message.data.get("tool_calls", [])
            ai_message_text = self.ai_message.text or ""

        if not raw_tool_calls:
            self.log("No tool calls found in AI message")
            return DataFrame(message_rows)

        # Add the AI message row (with tool_calls)
        ai_row = {
            "text": ai_message_text,
            "sender": "Machine",
            "sender_name": "AI",
            "tool_calls": raw_tool_calls,
            "has_tool_calls": True,
            "tool_call_id": None,
            "is_tool_result": False,
        }
        message_rows.append(ai_row)

        # Get available tools and execute
        tools = self.tools if isinstance(self.tools, list) else [self.tools]
        tools_by_name = {getattr(t, "name", ""): t for t in tools}

        tool_count = 0
        for tc in raw_tool_calls:
            result = await self._execute_single_tool_call(tc, tools_by_name)

            # Extract tool info
            tool_call_id = result.data.get("tool_call_id", "")
            tool_name = result.data.get("tool_name", "unknown")

            # Format result content
            if "error" in result.data:
                content = f"Error: {result.data['error']}"
            else:
                content = self._format_result_content(result.data.get("result", ""))

            # Add tool result row
            tool_row = {
                "text": content,
                "sender": "Tool",
                "sender_name": tool_name,
                "tool_calls": None,
                "has_tool_calls": False,
                "tool_call_id": tool_call_id,
                "is_tool_result": True,
            }
            message_rows.append(tool_row)
            tool_count += 1

        self.log(f"Executed {tool_count} tool(s)")
        return DataFrame(message_rows)

    async def _execute_single_tool_call(self, tc: Any, tools_by_name: dict) -> Data:
        """Execute a single tool call."""
        # Extract tool call info (handle both dict and object formats)
        if isinstance(tc, dict):
            tool_name = tc.get("name", "")
            tool_args = tc.get("args", {})
            tool_call_id = tc.get("id", "")
        else:
            tool_name = getattr(tc, "name", "")
            tool_args = getattr(tc, "args", {})
            tool_call_id = getattr(tc, "id", "")

        if not tool_name:
            return Data(
                data={
                    "error": "Tool call missing name",
                    "tool_call_id": tool_call_id,
                }
            )

        # Find the matching tool
        matching_tool = tools_by_name.get(tool_name)

        if matching_tool is None:
            return Data(
                data={
                    "error": f"Tool '{tool_name}' not found",
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "available_tools": list(tools_by_name.keys()),
                }
            )

        # Execute the tool
        try:
            result = await self._execute_tool_async(matching_tool, tool_args)

            return Data(
                data={
                    "result": result,
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "args": tool_args,
                }
            )

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
            return Data(
                data={
                    "error": str(e),
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "args": tool_args,
                }
            )

    async def _execute_tool_async(self, tool: Any, args: dict) -> Any:
        """Execute a tool, handling both sync and async tools."""
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
            import asyncio
            import inspect

            if inspect.iscoroutinefunction(tool):
                return await tool(**args)
            # Run sync callable in executor
            return await asyncio.to_thread(tool, **args)

        msg = f"Tool {tool} is not executable"
        raise TypeError(msg)

    def _format_result_content(self, result: Any) -> str:
        """Format a tool result as a string."""
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            import json

            return json.dumps(result, indent=2)
        if isinstance(result, list):
            import json

            return json.dumps(result, indent=2)
        return str(result)
