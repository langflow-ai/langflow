"""ExecuteTool component - executes tool calls from an AI message.

This component takes an AI message with tool_calls and the available tools,
executes them, and returns the AI message plus tool results as a DataFrame.
The WhileLoop handles accumulating these with the existing conversation history.

Features:
- Parallel execution: Multiple tool calls execute concurrently (configurable)
- Timeout: Individual tool calls can timeout to prevent hanging
- Reliable events: Tool call IDs ensure correct start/end event correlation
"""

from __future__ import annotations

import asyncio
import uuid
from time import perf_counter
from typing import Any

from lfx.base.agents.tool_execution import (
    build_ai_message_row,
    build_tool_result_row,
    build_tools_by_name,
    execute_tool,
    extract_tool_call_info,
)
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, IntInput
from lfx.io import HandleInput, MessageInput, Output
from lfx.schema.content_block import ContentBlock
from lfx.schema.content_types import ToolContent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI


class ExecuteToolComponent(Component):
    """Executes tool calls and returns AI message + tool results.

    This component:
    1. Takes a message containing tool_calls (from Agent Step)
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
            name="tool_calls_message",
            display_name="Tool Calls",
            info="Message containing tool_calls to execute (from Agent Step).",
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
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="Maximum time in seconds for each tool execution. 0 means no timeout.",
            value=0,
            advanced=True,
        ),
        BoolInput(
            name="parallel",
            display_name="Parallel Execution",
            info="Execute multiple tool calls concurrently for faster execution.",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Messages",
            name="messages",
            method="execute_tools",
        ),
    ]

    def _get_or_create_agent_message(self) -> Message:
        """Get the existing message or create a new one for tool execution updates.

        The event manager updates messages in the DB by ID. If we have a _parent_message
        from AgentLoop, use that. Otherwise, if the incoming tool_calls_message has an ID
        (from AgentStep's send_message), we should use it to update that message with
        tool execution content_blocks. This ensures all updates go to the same message in the UI.
        """
        # Check if we have a parent message from AgentLoop - use it directly
        parent_message: Message | None = getattr(self, "_parent_message", None)
        if parent_message:
            # Ensure parent message has an "Agent Steps" content block
            if not parent_message.content_blocks:
                parent_message.content_blocks = [ContentBlock(title="Agent Steps", contents=[])]
            else:
                has_agent_steps = any(
                    getattr(cb, "title", None) == "Agent Steps" for cb in parent_message.content_blocks
                )
                if not has_agent_steps:
                    parent_message.content_blocks.append(ContentBlock(title="Agent Steps", contents=[]))
            return parent_message

        # Get session_id from graph if available
        if hasattr(self, "graph") and self.graph:
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = uuid.uuid4()

        # Check if incoming ai_message has an ID we should reuse
        existing_id = None
        existing_content_blocks = None
        if self.tool_calls_message is not None:
            # Use getattr with None default - id may not exist on all message types
            try:
                existing_id = getattr(self.tool_calls_message, "id", None)
            except (AttributeError, KeyError):
                existing_id = None
            # Preserve existing content_blocks if any
            try:
                existing_content_blocks = getattr(self.tool_calls_message, "content_blocks", None)
            except (AttributeError, KeyError):
                existing_content_blocks = None

        # Prepare content_blocks: use existing or create new "Agent Steps" block
        if existing_content_blocks:
            content_blocks = list(existing_content_blocks)
            # Check if we already have an "Agent Steps" block
            has_agent_steps = any(getattr(cb, "title", None) == "Agent Steps" for cb in content_blocks)
            if not has_agent_steps:
                # Add a new block for tool execution steps
                content_blocks.append(ContentBlock(title="Agent Steps", contents=[]))
        else:
            content_blocks = [ContentBlock(title="Agent Steps", contents=[])]

        # Create message with or without existing ID
        message = Message(
            text=self.tool_calls_message.text if self.tool_calls_message else "",
            sender=MESSAGE_SENDER_AI,
            sender_name="AI",
            properties={"icon": "Bot", "state": "partial"},
            content_blocks=content_blocks,
            session_id=session_id,
        )

        # If we have an existing ID, set it so updates go to the same message
        if existing_id:
            message.id = existing_id

        return message

    def _get_agent_steps_block(self, agent_message: Message) -> ContentBlock | None:
        """Find the 'Agent Steps' content block in the message."""
        if not agent_message.content_blocks:
            return None
        for block in agent_message.content_blocks:
            if getattr(block, "title", None) == "Agent Steps":
                return block
        # Fallback to first block if no "Agent Steps" found
        return agent_message.content_blocks[0] if agent_message.content_blocks else None

    def _should_stream_events(self) -> bool:
        """Determine if tool events should be streamed to the frontend.

        This checks the 'should_stream_events' flag passed from CallModel via the AI message.
        CallModel knows if the agent flow is connected to a ChatOutput and passes that info.

        If the flag is not present (e.g., in tests or standalone usage), defaults to True
        when there's no vertex (standalone) or False when there is one (assume nested).
        """
        # Check flag from CallModel via ai_message
        if self.tool_calls_message is not None and hasattr(self.tool_calls_message, "data"):
            should_stream = self.tool_calls_message.data.get("should_stream_events")
            if should_stream is not None:
                return should_stream

        # Fallback: if no vertex, assume standalone (stream events)
        # If vertex exists but no flag, assume nested (don't stream)
        return self._vertex is None

    async def _send_tool_event(self, message: Message) -> Message:
        """Send tool execution event to the frontend if streaming is enabled.

        Events are sent based on the 'should_stream_events' flag from CallModel,
        which knows whether the agent flow is connected to a ChatOutput.
        This prevents nested agents (used as tools) from flooding the UI.
        """
        if not self._should_stream_events():
            return message

        # Ensure required fields are set
        self._ensure_message_required_fields(message)
        # Send event directly to frontend
        await self._send_message_event(message)
        return message

    async def _emit_tool_start(
        self,
        agent_message: Message,
        tool_name: str,
        tool_input: dict[str, Any],
        duration: int,
    ) -> tuple[Message, ToolContent]:
        """Emit tool start event via send_message with content_blocks update."""
        tool_content = ToolContent(
            type="tool_use",
            name=tool_name,
            tool_input=tool_input,
            output=None,
            error=None,
            header={"title": f"Accessing **{tool_name}**", "icon": "Hammer"},
            duration=duration,
        )

        steps_block = self._get_agent_steps_block(agent_message)
        if steps_block:
            steps_block.contents.append(tool_content)
            # Send update to frontend - bypasses _should_skip_message
            agent_message = await self._send_tool_event(agent_message)
            # Get the updated tool_content reference from the message
            updated_block = self._get_agent_steps_block(agent_message)
            if updated_block and updated_block.contents:
                tool_content = updated_block.contents[-1]

        return agent_message, tool_content

    async def _emit_tool_end(
        self,
        agent_message: Message,
        tool_content: ToolContent,
        output: Any,
        duration: int,
    ) -> Message:
        """Update tool content with result and emit via send_message with content_blocks update."""
        steps_block = self._get_agent_steps_block(agent_message)
        if steps_block:
            # Find and update the tool content by matching name AND tool_input
            # This handles multiple calls to the same tool
            for content in steps_block.contents:
                if (
                    isinstance(content, ToolContent)
                    and content.name == tool_content.name
                    and content.tool_input == tool_content.tool_input
                    and content.output is None  # Only update if not already completed
                ):
                    content.duration = duration
                    content.header = {"title": f"Executed **{content.name}**", "icon": "Hammer"}
                    content.output = output
                    break

            # Send update to frontend - bypasses _should_skip_message
            agent_message = await self._send_tool_event(agent_message)

        return agent_message

    async def _emit_tool_error(
        self,
        agent_message: Message,
        tool_content: ToolContent,
        error: str,
        duration: int,
    ) -> Message:
        """Update tool content with error and emit via send_message with content_blocks update."""
        steps_block = self._get_agent_steps_block(agent_message)
        if steps_block:
            # Find and update the tool content by matching name AND tool_input
            # This handles multiple calls to the same tool
            for content in steps_block.contents:
                if (
                    isinstance(content, ToolContent)
                    and content.name == tool_content.name
                    and content.tool_input == tool_content.tool_input
                    and content.error is None  # Only update if not already errored
                ):
                    content.duration = duration
                    content.header = {"title": f"Error using **{content.name}**", "icon": "Hammer"}
                    content.error = error
                    break

            # Send update to frontend - bypasses _should_skip_message
            agent_message = await self._send_tool_event(agent_message)

        return agent_message

    async def execute_tools(self) -> DataFrame:
        """Execute all tool calls and return AI message + tool results.

        Supports parallel execution (default) for faster processing of multiple tool calls.
        Each tool call has a unique tool_call_id for reliable event correlation.
        """
        # Build message rows for just the new messages (AI + tool results)
        message_rows: list[dict] = []

        # Get tool_calls from AI message
        raw_tool_calls = []
        ai_message_text = ""
        if self.tool_calls_message is not None:
            if hasattr(self.tool_calls_message, "data") and self.tool_calls_message.data:
                raw_tool_calls = self.tool_calls_message.data.get("tool_calls", [])
            ai_message_text = self.tool_calls_message.text or ""

        if not raw_tool_calls:
            self.log("No tool calls found in AI message")
            return DataFrame(message_rows)

        # Get the message ID from incoming ai_message to pass through the loop
        ai_message_id = None
        if self.tool_calls_message is not None:
            try:
                ai_message_id = getattr(self.tool_calls_message, "id", None)
            except (AttributeError, KeyError):
                ai_message_id = None

        # Get available tools using shared function
        tools = self.tools if isinstance(self.tools, list) else [self.tools]
        tools_by_name = build_tools_by_name(tools)

        # Get or create agent message for real-time updates
        agent_message = self._get_or_create_agent_message()
        agent_message = await self._send_tool_event(agent_message)

        # Pre-extract all tool call info for reliable event handling
        tool_call_infos = []
        for tc in raw_tool_calls:
            tool_name, tool_args, tool_call_id = extract_tool_call_info(tc)
            tool_call_infos.append(
                {
                    "raw": tc,
                    "name": tool_name,
                    "args": tool_args,
                    "tool_call_id": tool_call_id,
                }
            )

        # Find existing or create ToolContent items for each tool call
        # AgentStep may have already created "Accessing" ToolContent during streaming
        tool_contents: dict[str, ToolContent] = {}
        steps_block = self._get_agent_steps_block(agent_message)

        for info in tool_call_infos:
            tool_name = info["name"]
            tool_args = info["args"]

            # Check if there's already an "Accessing" ToolContent for this tool
            # that we can update (created by AgentStep during streaming)
            existing_content = None
            if steps_block:
                for content in steps_block.contents:
                    if (
                        isinstance(content, ToolContent)
                        and content.name == tool_name
                        and content.output is None  # Not yet completed
                        and content.error is None  # Not errored
                        and content.tool_input == {}  # Created by AgentStep with empty args
                    ):
                        existing_content = content
                        break

            if existing_content:
                # Update existing ToolContent with actual args
                existing_content.tool_input = tool_args
                tool_content = existing_content
            else:
                # Create new ToolContent (e.g., when not streaming or tool not detected during stream)
                tool_content = ToolContent(
                    type="tool_use",
                    name=tool_name,
                    tool_input=tool_args,
                    output=None,
                    error=None,
                    header={"title": f"Accessing **{tool_name}**", "icon": "Hammer"},
                    duration=0,
                )
                if steps_block:
                    steps_block.contents.append(tool_content)

            tool_contents[info["tool_call_id"]] = tool_content

        # Emit start events (updates existing or shows new)
        agent_message = await self._send_tool_event(agent_message)

        # Execute tools (parallel or sequential)
        if self.parallel and len(tool_call_infos) > 1:
            results = await self._execute_tools_parallel(tool_call_infos, tools_by_name)
        else:
            results = await self._execute_tools_sequential(tool_call_infos, tools_by_name)

        # Update ToolContent items with results and emit end events
        for result in results:
            tool_call_id = result.data.get("tool_call_id", "")
            tool_content = tool_contents.get(tool_call_id)
            if tool_content:
                error = result.data.get("error")
                if error:
                    tool_content.error = error
                    tool_content.header = {"title": f"Error using **{tool_content.name}**", "icon": "Hammer"}
                else:
                    tool_content.output = str(result.data.get("result", ""))
                    tool_content.header = {"title": f"Executed **{tool_content.name}**", "icon": "Hammer"}
                tool_content.duration = result.data.get("duration_ms", 0)

        # Emit all end events
        agent_message = await self._send_tool_event(agent_message)

        # Mark agent message as complete
        if agent_message.properties:
            agent_message.properties.state = "complete"
        await self._send_tool_event(agent_message)

        # Build result rows
        tool_result_rows = []
        for result in results:
            tool_call_id = result.data.get("tool_call_id", "")
            tool_name = result.data.get("tool_name", "unknown")
            error = result.data.get("error")
            tool_result = result.data.get("result", "") if not error else None
            tool_result_rows.append(build_tool_result_row(tool_name, tool_call_id, tool_result, error))

        # Build the AI message row with content_blocks
        content_blocks = agent_message.content_blocks if agent_message.content_blocks else None
        message_rows.append(build_ai_message_row(ai_message_text, raw_tool_calls, ai_message_id, content_blocks))
        message_rows.extend(tool_result_rows)

        self.log(f"Executed {len(results)} tool(s)" + (" in parallel" if self.parallel else " sequentially"))
        return DataFrame(message_rows)

    async def _execute_tools_parallel(
        self,
        tool_call_infos: list[dict],
        tools_by_name: dict,
    ) -> list[Data]:
        """Execute all tool calls in parallel using asyncio.gather."""
        tasks = [self._execute_tool_with_timeout(info, tools_by_name) for info in tool_call_infos]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error Data objects
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                info = tool_call_infos[i]
                final_results.append(
                    Data(
                        data={
                            "error": str(result),
                            "tool_name": info["name"],
                            "tool_call_id": info["tool_call_id"],
                            "args": info["args"],
                            "duration_ms": 0,
                        }
                    )
                )
            else:
                final_results.append(result)
        return final_results

    async def _execute_tools_sequential(
        self,
        tool_call_infos: list[dict],
        tools_by_name: dict,
    ) -> list[Data]:
        """Execute tool calls sequentially."""
        results = []
        for info in tool_call_infos:
            result = await self._execute_tool_with_timeout(info, tools_by_name)
            results.append(result)
        return results

    async def _execute_tool_with_timeout(
        self,
        info: dict,
        tools_by_name: dict,
    ) -> Data:
        """Execute a single tool call with optional timeout."""
        tool_name = info["name"]
        tool_args = info["args"]
        tool_call_id = info["tool_call_id"]
        start_time = perf_counter()

        if not tool_name:
            return Data(
                data={
                    "error": "Tool call missing name",
                    "tool_call_id": tool_call_id,
                    "duration_ms": 0,
                }
            )

        matching_tool = tools_by_name.get(tool_name)
        if matching_tool is None:
            return Data(
                data={
                    "error": f"Tool '{tool_name}' not found",
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "available_tools": list(tools_by_name.keys()),
                    "duration_ms": int((perf_counter() - start_time) * 1000),
                }
            )

        try:
            # Execute with timeout if configured
            if self.timeout and self.timeout > 0:
                result = await asyncio.wait_for(
                    execute_tool(matching_tool, tool_args),
                    timeout=self.timeout,
                )
            else:
                result = await execute_tool(matching_tool, tool_args)

            duration_ms = int((perf_counter() - start_time) * 1000)
            return Data(
                data={
                    "result": result,
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "args": tool_args,
                    "duration_ms": duration_ms,
                }
            )

        except asyncio.TimeoutError:
            duration_ms = int((perf_counter() - start_time) * 1000)
            return Data(
                data={
                    "error": f"Tool '{tool_name}' timed out after {self.timeout}s",
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "args": tool_args,
                    "duration_ms": duration_ms,
                }
            )

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
            duration_ms = int((perf_counter() - start_time) * 1000)
            return Data(
                data={
                    "error": str(e),
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "args": tool_args,
                    "duration_ms": duration_ms,
                }
            )
