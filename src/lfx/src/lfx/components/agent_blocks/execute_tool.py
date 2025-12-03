"""ExecuteTool component - executes all tool calls from an AI message.

This component takes an AI message with tool_calls and the available tools,
finds the matching tools by name, and executes them with the provided arguments.
"""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import HandleInput, MessageInput, Output
from lfx.schema.data import Data


class ExecuteToolComponent(Component):
    """Executes all tool calls from an AI message.

    This component:
    1. Takes an AI message containing tool_calls
    2. Finds matching tools from the provided tools list
    3. Executes all tools with their arguments
    4. Returns results as a list of Data objects

    Each result includes the tool call ID so results can be matched back.
    The first result also includes the original AI message data for FormatResult.
    """

    display_name = "Execute Tool"
    description = "Execute all tool calls from an AI message."
    icon = "play"
    category = "agent_blocks"

    inputs = [
        MessageInput(
            name="ai_message",
            display_name="AI Message",
            info="The AI message containing tool_calls to execute.",
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
            display_name="Tool Results",
            name="tool_results",
            method="execute_tools",
        ),
    ]

    async def execute_tools(self) -> list[Data]:
        """Execute all tool calls and return the results."""
        if self.ai_message is None:
            return [Data(data={"error": "No AI message provided"})]

        # Get tool_calls from message data
        raw_tool_calls = []
        if hasattr(self.ai_message, "data") and self.ai_message.data:
            raw_tool_calls = self.ai_message.data.get("tool_calls", [])

        if not raw_tool_calls:
            return [Data(data={"error": "No tool calls found in AI message"})]

        # Get available tools
        tools = self.tools if isinstance(self.tools, list) else [self.tools]
        tools_by_name = {getattr(t, "name", ""): t for t in tools}

        results = []
        for tc in raw_tool_calls:
            result = await self._execute_single_tool_call(tc, tools_by_name)
            results.append(result)

        # Include AI message data in the first result for FormatResult to use
        if results:
            results[0].data["ai_message_text"] = self.ai_message.text or ""
            results[0].data["ai_message_tool_calls"] = raw_tool_calls

        tool_names = [r.data.get("tool_name", "unknown") for r in results]
        self.log(f"Executed {len(results)} tool(s): {', '.join(tool_names)}")
        return results

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
