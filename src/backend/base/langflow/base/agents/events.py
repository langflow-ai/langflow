# Add helper functions for each event type
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


def _build_agent_input_text_content(agent_input_dict: InputDict) -> str:
    chat_history = agent_input_dict.get("chat_history", [])
    messages = [
        f"**{message.type.upper()}**: {message.content}"
        for message in chat_history
        if isinstance(message, BaseMessage) and message.content
    ]
    final_input = agent_input_dict.get("input", "")
    if messages and final_input not in messages[-1]:
        messages.append(f"**HUMAN**: {final_input}")
    return "  \n".join(messages)


def _calculate_duration(start_time: float) -> int:
    """Calculate duration in milliseconds from start time to now."""
    return int((perf_counter() - start_time) * 1000)


def handle_on_chain_start(event: dict[str, Any], agent_message: Message) -> Message:
    # Create content blocks if they don't exist
    if not agent_message.content_blocks:
        agent_message.content_blocks = [ContentBlock(title="Agent Steps", contents=[])]

    if event["data"].get("input"):
        input_data = event["data"].get("input")
        if isinstance(input_data, dict) and "input" in input_data:
            # Cast the input_data to InputDict
            input_dict: InputDict = {
                "input": str(input_data.get("input", "")),
                "chat_history": input_data.get("chat_history", []),
            }
            text_content = TextContent(
                type="text",
                text=_build_agent_input_text_content(input_dict),
                duration=_calculate_duration(event["start_time"]),
                header={"title": "Input", "icon": "MessageSquare"},
            )
            agent_message.content_blocks[0].contents.append(text_content)
    return agent_message


def handle_on_chain_end(event: dict[str, Any], agent_message: Message) -> Message:
    data_output = event["data"].get("output")
    if data_output and isinstance(data_output, AgentFinish) and data_output.return_values.get("output"):
        agent_message.text = data_output.return_values.get("output")
        agent_message.properties.state = "complete"
        # Add duration to the last content if it exists
        if agent_message.content_blocks and agent_message.content_blocks[0].contents:
            last_content = agent_message.content_blocks[0].contents[-1]
            if not getattr(last_content, "duration", None):
                last_content.duration = _calculate_duration(event["start_time"])
    return agent_message


def handle_on_tool_start(
    event: dict[str, Any],
    agent_message: Message,
    tool_blocks_map: dict[str, ToolContent],
) -> Message:
    tool_name = event["name"]
    tool_input = event["data"].get("input")
    run_id = event.get("run_id", "")

    # Create content blocks if they don't exist
    if not agent_message.content_blocks:
        agent_message.content_blocks = [ContentBlock(title="Agent Steps", contents=[])]

    # Create new tool content with the input exactly as received
    tool_content = ToolContent(
        type="tool_use",
        name=tool_name,
        input=tool_input,
        output=None,
        error=None,
        header={"title": f"Accessing **{tool_name}**", "icon": "Hammer"},
    )

    # Store in map and append to message
    tool_blocks_map[run_id] = tool_content
    agent_message.content_blocks[0].contents.append(tool_content)

    return agent_message


def handle_on_tool_end(
    event: dict[str, Any],
    agent_message: Message,
    tool_blocks_map: dict[str, ToolContent],
) -> Message:
    run_id = event.get("run_id", "")
    tool_content = tool_blocks_map.get(run_id)

    if tool_content and isinstance(tool_content, ToolContent):
        tool_content.output = event["data"].get("output")
        # Calculate duration only when tool ends
        tool_content.header = {"title": f"Executed **{tool_content.name}**", "icon": "Hammer"}
        tool_content.duration = _calculate_duration(event["start_time"])

    return agent_message


def handle_on_tool_error(
    event: dict[str, Any],
    agent_message: Message,
    tool_blocks_map: dict[str, ToolContent],
) -> Message:
    run_id = event.get("run_id", "")
    tool_content = tool_blocks_map.get(run_id)

    if tool_content and isinstance(tool_content, ToolContent):
        tool_content.error = event["data"].get("error", "Unknown error")
        tool_content.duration = _calculate_duration(event["start_time"])
        tool_content.header = {"title": f"Error using **{tool_content.name}**", "icon": "Hammer"}

    return agent_message


def handle_on_chain_stream(event: dict[str, Any], agent_message: Message) -> Message:
    data_chunk = event["data"].get("chunk", {})
    if isinstance(data_chunk, dict) and data_chunk.get("output"):
        agent_message.text = data_chunk.get("output")
        agent_message.properties.state = "complete"
    return agent_message


class ToolEventHandler(Protocol):
    def __call__(
        self,
        event: dict[str, Any],
        agent_message: Message,
        tool_blocks_map: dict[str, ContentBlock],
    ) -> Message: ...


class ChainEventHandler(Protocol):
    def __call__(
        self,
        event: dict[str, Any],
        agent_message: Message,
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
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
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
            # Pass the tool_blocks_map to tool handlers
            agent_message = tool_handler(event, agent_message, tool_blocks_map)
            agent_message = send_message_method(message=agent_message)
            tool_blocks_map = {**tool_blocks_map, event["run_id"]: agent_message.content_blocks[0].contents[-1]}
        elif event["event"] in CHAIN_EVENT_HANDLERS:
            chain_handler = CHAIN_EVENT_HANDLERS[event["event"]]
            agent_message = chain_handler(event, agent_message)
            agent_message = send_message_method(message=agent_message)

    agent_message.properties.state = "complete"
    return Message(**agent_message.model_dump())
