# Add helper functions for each event type
import asyncio
from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any, Protocol

from langchain_core.agents import AgentFinish
from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

from langflow.schema.content_block import ContentBlock
from langflow.schema.content_types import TextContent, ToolContent
from langflow.schema.log import SendMessageFunctionType
from langflow.schema.message import Message
from langflow.utils.constants import MESSAGE_SENDER_AI


class InputDict(TypedDict):
    input: str
    chat_history: list[BaseMessage]


def _build_agent_input_text_content(agent_input_dict: InputDict) -> ContentBlock:
    chat_history = agent_input_dict.get("chat_history", [])
    messages = [
        f"**{message.type.upper()}**: {message.content}"
        for message in chat_history
        if isinstance(message, BaseMessage) and message.content
    ]
    final_input = agent_input_dict.get("input", "")
    if final_input not in messages[-1]:
        messages.append(f"**HUMAN**: {final_input}")
    return "  \n".join(messages)


def _calculate_duration(start_time: float) -> int:
    """Calculate duration in milliseconds from start time to now."""
    return int((perf_counter() - start_time) * 1000)


def handle_on_chain_start(
    event: dict[str, Any], agent_message: Message, send_message_method: SendMessageFunctionType
) -> Message:
    if event["data"].get("input"):
        text_content = TextContent(
            type="text",
            text=_build_agent_input_text_content(event["data"].get("input")),
            duration=_calculate_duration(event.get("start_time", perf_counter())),
        )
        agent_message.content_blocks[0].contents.append(text_content)
        agent_message.properties.icon = "🚀"
        agent_message = send_message_method(message=agent_message)
    return agent_message


def handle_on_chain_end(
    event: dict[str, Any], agent_message: Message, send_message_method: SendMessageFunctionType
) -> Message:
    data_output = event["data"].get("output", {})
    if data_output:
        if isinstance(data_output, AgentFinish) and data_output.return_values.get("output"):
            agent_message.text = data_output.return_values.get("output")
            # Add duration to the last content if it exists
            if agent_message.content_blocks and agent_message.content_blocks[0].contents:
                last_content = agent_message.content_blocks[0].contents[-1]
                if not getattr(last_content, "duration", None):
                    last_content.duration = _calculate_duration(event.get("start_time", perf_counter()))
            agent_message.properties.icon = "Bot"
        else:
            agent_message.properties.icon = "CheckCircle"
        agent_message = send_message_method(message=agent_message)
    return agent_message


def _find_or_create_tool_content(
    tool_blocks_map: dict[str, ToolContent],
    run_id: str,
    tool_name: str,
    tool_input: Any | None = None,
    tool_output: Any | None = None,
    tool_error: Any | None = None,
) -> ToolContent:
    """Create a new ToolContent object."""
    tool_content = tool_blocks_map.get(tool_name)
    if not tool_content:
        tool_content = ToolContent(
            type="tool_use",
            name=tool_name,
            tool_input=tool_input,
            output=tool_output,
            error=tool_error,
        )
        tool_blocks_map[run_id] = tool_content
    return tool_content


def handle_on_tool_start(
    event: dict[str, Any],
    agent_message: Message,
    send_message_method: SendMessageFunctionType,
    tool_blocks_map: dict[str, ToolContent],
) -> Message:
    tool_name = event["name"]
    tool_input = event["data"].get("input")

    tool_content = _find_or_create_tool_content(
        tool_blocks_map, event.get("run_id", ""), tool_name, tool_input=tool_input
    )
    agent_message.content_blocks[0].contents.append(tool_content)

    agent_message.properties.icon = "Hammer"
    agent_message = send_message_method(message=agent_message)
    tool_blocks_map[event.get("run_id", "")] = agent_message.content_blocks[0].contents[-1]
    return agent_message


def handle_on_tool_end(
    event: dict[str, Any],
    agent_message: Message,
    send_message_method: SendMessageFunctionType,
    tool_blocks_map: dict[str, ContentBlock],
) -> Message:
    run_id = event.get("run_id", "")
    tool_content = tool_blocks_map.get(run_id)

    if tool_content and isinstance(tool_content, ToolContent):
        tool_content.output = event["data"].get("output")
        # Calculate duration only when tool ends
        tool_content.duration = _calculate_duration(event.get("start_time", perf_counter()))

    return send_message_method(message=agent_message)


def handle_on_tool_error(
    event: dict[str, Any],
    agent_message: Message,
    send_message_method: SendMessageFunctionType,
    tool_blocks_map: dict[str, ContentBlock],
) -> Message:
    run_id = event.get("run_id", "")
    tool_content = tool_blocks_map.get(run_id)

    if tool_content and isinstance(tool_content, ToolContent):
        tool_content.error = event["data"].get("error", "Unknown error")

    agent_message.properties.icon = "OctagonAlert"
    return send_message_method(message=agent_message)


def handle_on_chain_stream(
    event: dict[str, Any], agent_message: Message, send_message_method: SendMessageFunctionType
) -> Message:
    data_chunk = event["data"].get("chunk", {})
    if isinstance(data_chunk, dict) and data_chunk.get("output"):
        agent_message.text = data_chunk.get("output")
        agent_message.properties.state = "complete"
        agent_message = send_message_method(message=agent_message)
    return agent_message


class ToolEventHandler(Protocol):
    def __call__(
        self,
        event: dict[str, Any],
        agent_message: Message,
        send_message_method: SendMessageFunctionType,
        tool_blocks_map: dict[str, ContentBlock],
    ) -> Message: ...


class ChainEventHandler(Protocol):
    def __call__(
        self,
        event: dict[str, Any],
        agent_message: Message,
        send_message_method: SendMessageFunctionType,
    ) -> Message: ...


EventHandler = ToolEventHandler | ChainEventHandler

# Define separate mappings of event types to their respective handler functions
CHAIN_EVENT_HANDLERS: dict[str, ChainEventHandler] = {
    "on_chain_start": handle_on_chain_start,
    "on_chain_end": handle_on_chain_end,
    "on_chain_stream": handle_on_chain_stream,
}

TOOL_EVENT_HANDLERS: dict[str, ToolEventHandler] = {
    "on_tool_start": handle_on_tool_start,
    "on_tool_end": handle_on_tool_end,
    "on_tool_error": handle_on_tool_error,
}


async def process_agent_events(
    agent_executor: AsyncIterator[dict[str, Any]],
    send_message_method: SendMessageFunctionType,
) -> Message:
    """Process agent events and return the final output."""
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Execution", contents=[])],
    )
    # Store the initial message
    agent_message = send_message_method(message=agent_message)

    # Create a mapping of run_ids to tool contents
    tool_blocks_map: dict[str, ToolContent] = {}

    async for event in agent_executor:
        # Add start_time to event
        event["start_time"] = perf_counter()

        if event["event"] in TOOL_EVENT_HANDLERS:
            tool_handler = TOOL_EVENT_HANDLERS[event["event"]]
            agent_message = await asyncio.to_thread(
                tool_handler, event, agent_message, send_message_method, tool_blocks_map
            )
        elif event["event"] in CHAIN_EVENT_HANDLERS:
            chain_handler = CHAIN_EVENT_HANDLERS[event["event"]]
            agent_message = await asyncio.to_thread(chain_handler, event, agent_message, send_message_method)
        else:
            # Handle any other event types or ignore them
            pass

    agent_message.properties.state = "complete"
    return Message(**agent_message.model_dump())
