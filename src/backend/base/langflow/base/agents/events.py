# Add helper functions for each event type
from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any, Protocol, AsyncGenerator, Callable, Dict, Optional

from langchain_core.agents import AgentFinish
from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

from langflow.schema.content_block import ContentBlock
from langflow.schema.content_types import TextContent, ToolContent
from langflow.schema.log import SendMessageFunctionType
from langflow.schema.message import Message
from langflow.utils.constants import MESSAGE_SENDER_AI


class ExceptionWithMessageError(Exception):
    def __init__(self, agent_message: Message, message: str):
        self.agent_message = agent_message
        super().__init__(message)
        self.message = message

    def __str__(self):
        return (
            f"Agent message: {self.agent_message.text} \nError: {self.message}."
            if self.agent_message.error or self.agent_message.text
            else f"{self.message}."
        )


class InputDict(TypedDict):
    input: str
    chat_history: list[BaseMessage]


def _build_agent_input_text_content(agent_input_dict: InputDict) -> str:
    final_input = agent_input_dict.get("input", "")
    return f"**Input**: {final_input}"


def _calculate_duration(start_time: float) -> int:
    """Calculate duration in milliseconds from start time to now."""
    # Handle the calculation
    current_time = perf_counter()
    if isinstance(start_time, int):
        # If we got an integer, treat it as milliseconds
        duration = current_time - (start_time / 1000)
        result = int(duration * 1000)
    else:
        # If we got a float, treat it as perf_counter time
        result = int((current_time - start_time) * 1000)

    return result


async def handle_on_chain_start(
    event: dict[str, Any], agent_message: Message, send_message_method: SendMessageFunctionType, start_time: float
) -> tuple[Message, float]:
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
                duration=_calculate_duration(start_time),
                header={"title": "Input", "icon": "MessageSquare"},
            )
            agent_message.content_blocks[0].contents.append(text_content)
            agent_message = await send_message_method(message=agent_message)
            start_time = perf_counter()
    return agent_message, start_time


def _extract_output_text(output: str | list) -> str:
    if isinstance(output, str):
        text = output
    elif isinstance(output, list) and len(output) == 1 and isinstance(output[0], dict) and "text" in output[0]:
        text = output[0]["text"]
    else:
        msg = f"Output is not a string or list of dictionaries with 'text' key: {output}"
        raise ValueError(msg)
    return text


async def handle_on_chain_end(
    event: dict[str, Any], agent_message: Message, send_message_method: SendMessageFunctionType, start_time: float
) -> tuple[Message, float]:
    data_output = event["data"].get("output")
    if data_output and isinstance(data_output, AgentFinish) and data_output.return_values.get("output"):
        output = data_output.return_values.get("output")

        agent_message.text = _extract_output_text(output)
        agent_message.properties.state = "complete"
        # Add duration to the last content if it exists
        if agent_message.content_blocks:
            duration = _calculate_duration(start_time)
            text_content = TextContent(
                type="text",
                text=agent_message.text,
                duration=duration,
                header={"title": "Output", "icon": "MessageSquare"},
            )
            agent_message.content_blocks[0].contents.append(text_content)
        agent_message = await send_message_method(message=agent_message)
        start_time = perf_counter()
    return agent_message, start_time


async def handle_on_tool_start(
    event: dict[str, Any],
    agent_message: Message,
    tool_blocks_map: dict[str, ToolContent],
    send_message_method: SendMessageFunctionType,
    start_time: float,
) -> tuple[Message, float]:
    tool_name = event["name"]
    tool_input = event["data"].get("input")
    run_id = event.get("run_id", "")
    tool_key = f"{tool_name}_{run_id}"

    # Create content blocks if they don't exist
    if not agent_message.content_blocks:
        agent_message.content_blocks = [ContentBlock(title="Agent Steps", contents=[])]

    duration = _calculate_duration(start_time)
    new_start_time = perf_counter()  # Get new start time for next operation

    # Create new tool content with the input exactly as received
    tool_content = ToolContent(
        type="tool_use",
        name=tool_name,
        input=tool_input,
        output=None,
        error=None,
        header={"title": f"Accessing **{tool_name}**", "icon": "Hammer"},
        duration=duration,  # Store the actual duration
    )

    # Store in map and append to message
    tool_blocks_map[tool_key] = tool_content
    agent_message.content_blocks[0].contents.append(tool_content)

    agent_message = await send_message_method(message=agent_message)
    if agent_message.content_blocks and agent_message.content_blocks[0].contents:
        tool_blocks_map[tool_key] = agent_message.content_blocks[0].contents[-1]
    return agent_message, new_start_time


async def handle_on_tool_end(
    event: dict[str, Any],
    agent_message: Message,
    tool_blocks_map: dict[str, ToolContent],
    send_message_method: SendMessageFunctionType,
    start_time: float,
) -> tuple[Message, float]:
    run_id = event.get("run_id", "")
    tool_name = event.get("name", "")
    tool_key = f"{tool_name}_{run_id}"
    tool_content = tool_blocks_map.get(tool_key)

    if tool_content and isinstance(tool_content, ToolContent):
        tool_content.output = event["data"].get("output")
        duration = _calculate_duration(start_time)
        tool_content.duration = duration
        tool_content.header = {"title": f"Executed **{tool_content.name}**", "icon": "Hammer"}

        agent_message = await send_message_method(message=agent_message)
        new_start_time = perf_counter()  # Get new start time for next operation
        return agent_message, new_start_time
    return agent_message, start_time


async def handle_on_tool_error(
    event: dict[str, Any],
    agent_message: Message,
    tool_blocks_map: dict[str, ToolContent],
    send_message_method: SendMessageFunctionType,
    start_time: float,
) -> tuple[Message, float]:
    run_id = event.get("run_id", "")
    tool_name = event.get("name", "")
    tool_key = f"{tool_name}_{run_id}"
    tool_content = tool_blocks_map.get(tool_key)

    if tool_content and isinstance(tool_content, ToolContent):
        tool_content.error = event["data"].get("error", "Unknown error")
        tool_content.duration = _calculate_duration(start_time)
        tool_content.header = {"title": f"Error using **{tool_content.name}**", "icon": "Hammer"}
        agent_message = await send_message_method(message=agent_message)
        start_time = perf_counter()
    return agent_message, start_time


async def handle_on_chain_stream(
    event: dict[str, Any],
    agent_message: Message,
    send_message_method: SendMessageFunctionType,
    start_time: float,
) -> tuple[Message, float]:
    data_chunk = event["data"].get("chunk", {})
    if isinstance(data_chunk, dict) and data_chunk.get("output"):
        output = data_chunk.get("output")
        if output and isinstance(output, str | list):
            agent_message.text = _extract_output_text(output)
        agent_message.properties.state = "complete"
        agent_message = await send_message_method(message=agent_message)
        start_time = perf_counter()
    return agent_message, start_time


class ToolEventHandler(Protocol):
    async def __call__(
        self,
        event: dict[str, Any],
        agent_message: Message,
        tool_blocks_map: dict[str, ContentBlock],
        send_message_method: SendMessageFunctionType,
        start_time: float,
    ) -> tuple[Message, float]: ...


class ChainEventHandler(Protocol):
    async def __call__(
        self,
        event: dict[str, Any],
        agent_message: Message,
        send_message_method: SendMessageFunctionType,
        start_time: float,
    ) -> tuple[Message, float]: ...


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
    agent_message: Message,
    send_message_method: SendMessageFunctionType,
) -> Message:
    """Process agent events and return the final output."""
    if isinstance(agent_message.properties, dict):
        agent_message.properties.update({"icon": "Bot", "state": "partial"})
    else:
        agent_message.properties.icon = "Bot"
        agent_message.properties.state = "partial"
    # Store the initial message
    agent_message = await send_message_method(message=agent_message)
    try:
        # Create a mapping of run_ids to tool contents
        tool_blocks_map: dict[str, ToolContent] = {}
        start_time = perf_counter()
        async for event in agent_executor:
            if event["event"] in TOOL_EVENT_HANDLERS:
                tool_handler = TOOL_EVENT_HANDLERS[event["event"]]
                agent_message, start_time = await tool_handler(
                    event, agent_message, tool_blocks_map, send_message_method, start_time
                )
            elif event["event"] in CHAIN_EVENT_HANDLERS:
                chain_handler = CHAIN_EVENT_HANDLERS[event["event"]]
                agent_message, start_time = await chain_handler(event, agent_message, send_message_method, start_time)
        agent_message.properties.state = "complete"
    except Exception as e:
        raise ExceptionWithMessageError(agent_message, str(e)) from e
    return await Message.create(**agent_message.model_dump())


async def process_smol_agent_events(
    agent_executor: AsyncGenerator[Any, None] | Any,
    agent_message: Message,
    send_message_method: Callable,
) -> Message:
    """Process events from a SMOL agent and update the message accordingly."""
    # Initialize message with proper state
    if isinstance(agent_message.properties, dict):
        agent_message.properties.update({"icon": "Bot", "state": "partial"})
    else:
        agent_message.properties.icon = "Bot"
        agent_message.properties.state = "partial"
    
    # Initialize content blocks if they don't exist
    if not agent_message.content_blocks:
        agent_message.content_blocks = [
            ContentBlock(
                title="Agent Steps",
                contents=[
                    TextContent(
                        type="text",
                        text="Starting SMOL agent...",
                        header={"title": "Initialization", "icon": "Bot"}
                    )
                ]
            )
        ]
    
    # Store the initial message
    try:
        agent_message = await send_message_method(message=agent_message)
    except Exception as e:
        error_message = f"Failed to send initial message: {str(e)}"
        agent_message.properties.state = "complete"
        agent_message.error = True
        raise ExceptionWithMessageError(agent_message, error_message) from e

    try:
        # Create a mapping of run_ids to tool contents
        tool_blocks_map: dict[str, ToolContent] = {}
        start_time = perf_counter()

        # Convert regular generator to async generator if needed
        async def aiter():
            try:
                if hasattr(agent_executor, "__aiter__"):
                    async for event in agent_executor:
                        if event is None:
                            continue
                        yield event
                else:
                    for event in agent_executor:
                        if event is None:
                            continue
                        yield event
            except Exception as e:
                error_message = str(e)
                if "code parsing" in error_message.lower():
                    # Extract the code snippet if available
                    code_snippet = ""
                    if "Here is your code snippet:" in error_message:
                        parts = error_message.split("Here is your code snippet:")
                        if len(parts) > 1:
                            code_snippet = parts[1].strip()
                    
                    error_message = (
                        f"Code Parsing Error: {error_message}\n\n"
                        f"The provided code:\n{code_snippet}\n\n"
                        "Please ensure your code follows this exact format:\n"
                        "Thoughts: Your reasoning about the task\n"
                        "Code:\n```python\n# Your Python code here\n```<end_code>\n\n"
                        "Common issues to check:\n"
                        "1. Missing 'Thoughts:' section\n"
                        "2. Incorrect code block format\n"
                        "3. Missing <end_code> tag\n"
                        "4. Improper indentation"
                    )
                
                error_content = TextContent(
                    type="text",
                    text=error_message,
                    duration=_calculate_duration(start_time),
                    header={"title": "Error", "icon": "AlertTriangle"},
                )
                agent_message.content_blocks.append(
                    ContentBlock(
                        title="Error",
                        contents=[error_content],
                    )
                )
                agent_message.properties.state = "complete"
                agent_message.error = True
                await send_message_method(agent_message)
                raise ExceptionWithMessageError(agent_message, error_message) from e

        async for event in aiter():
            # Handle PlanningStep events
            if hasattr(event, "plan"):
                try:
                    plan_content = TextContent(
                        type="text",
                        text=event.plan,
                        duration=_calculate_duration(start_time),
                        header={"title": "Planning", "icon": "Plan"},
                    )
                    agent_message.content_blocks.append(
                        ContentBlock(
                            title="Planning",
                            contents=[plan_content],
                        )
                    )
                    if hasattr(event, "facts"):
                        facts_content = TextContent(
                            type="text",
                            text=event.facts,
                            duration=_calculate_duration(start_time),
                            header={"title": "Facts", "icon": "Info"},
                        )
                        agent_message.content_blocks.append(
                            ContentBlock(
                                title="Facts",
                                contents=[facts_content],
                            )
                        )
                    await send_message_method(agent_message)
                    continue
                except Exception as e:
                    error_message = f"Error processing planning step: {str(e)}"
                    raise ExceptionWithMessageError(agent_message, error_message) from e

            # Handle ActionStep events with tool execution
            if hasattr(event, "tool_calls") and event.tool_calls:
                for tool_call in event.tool_calls:
                    try:
                        # Convert arguments to dictionary if it's a string
                        tool_input = tool_call.arguments
                        if isinstance(tool_input, str):
                            # Check if this is Python code
                            if tool_call.name == "python_interpreter":
                                # Validate code format
                                if not tool_input.strip().startswith("Thoughts:"):
                                    tool_input = f"Thoughts: Executing the following code\nCode:\n```python\n{tool_input}\n```<end_code>"
                                tool_input = {"code": tool_input}
                            else:
                                tool_input = {"input": tool_input}
                        
                        # Tool start
                        tool_content = ToolContent(
                            type="tool_use",
                            name=tool_call.name,
                            input=tool_input,
                            output=None,
                            error=None,
                            header={"title": f"Using **{tool_call.name}**", "icon": "Hammer"},
                            duration=_calculate_duration(start_time),
                        )
                        tool_blocks_map[tool_call.id] = tool_content
                        agent_message.content_blocks.append(
                            ContentBlock(
                                title="Tool Execution",
                                contents=[tool_content],
                            )
                        )
                        await send_message_method(agent_message)

                        # Tool end
                        if hasattr(event, "observations"):
                            tool_content.output = str(event.observations)
                            tool_content.duration = _calculate_duration(start_time)
                            tool_content.header = {"title": f"Executed **{tool_call.name}**", "icon": "Hammer"}
                            await send_message_method(agent_message)
                    except Exception as e:
                        error_message = f"Error processing tool call {tool_call.name}: {str(e)}"
                        raise ExceptionWithMessageError(agent_message, error_message) from e

            # Handle final response
            if hasattr(event, "action_output") and event.action_output is not None:
                try:
                    output_text = str(event.action_output)
                    agent_message.content = output_text
                    agent_message.text = output_text  # Set text for playground display
                    agent_message.properties.state = "complete"
                    # Add final output as a content block too
                    output_content = TextContent(
                        type="text",
                        text=output_text,
                        duration=_calculate_duration(start_time),
                        header={"title": "Output", "icon": "MessageSquare"},
                    )
                    agent_message.content_blocks.append(
                        ContentBlock(
                            title="Output",
                            contents=[output_content],
                        )
                    )
                    await send_message_method(agent_message)
                    return agent_message
                except Exception as e:
                    error_message = f"Error processing final response: {str(e)}"
                    raise ExceptionWithMessageError(agent_message, error_message) from e

            # Handle errors
            if hasattr(event, "error") and event.error is not None:
                try:
                    error_message = str(event.error)
                    # Special handling for code parsing errors
                    if "code parsing" in error_message.lower():
                        # Extract the code snippet if available
                        code_snippet = ""
                        if "Here is your code snippet:" in error_message:
                            parts = error_message.split("Here is your code snippet:")
                            if len(parts) > 1:
                                code_snippet = parts[1].strip()
                        
                        error_message = (
                            f"Code Parsing Error:\n{code_snippet}\n\n"
                            "Please ensure your code follows this exact format:\n"
                            "Thoughts: Your reasoning about the task\n"
                            "Code:\n```python\n# Your Python code here\n```<end_code>\n\n"
                            "Common issues to check:\n"
                            "1. Missing 'Thoughts:' section\n"
                            "2. Incorrect code block format\n"
                            "3. Missing <end_code> tag\n"
                            "4. Improper indentation"
                        )
                    
                    # Set both content and text for proper display
                    agent_message.content = error_message
                    agent_message.text = error_message
                    
                    error_content = TextContent(
                        type="text",
                        text=error_message,
                        duration=_calculate_duration(start_time),
                        header={"title": "Error", "icon": "AlertTriangle"},
                    )
                    # Clear existing error blocks to prevent duplication
                    agent_message.content_blocks = [block for block in agent_message.content_blocks if block.title != "Error"]
                    agent_message.content_blocks.append(
                        ContentBlock(
                            title="Error",
                            contents=[error_content],
                        )
                    )
                    agent_message.properties.state = "complete"
                    agent_message.error = True
                    await send_message_method(agent_message)
                    raise ExceptionWithMessageError(agent_message, error_message)
                except Exception as e:
                    if not isinstance(e, ExceptionWithMessageError):
                        error_message = f"Error processing error event: {str(e)}"
                        raise ExceptionWithMessageError(agent_message, error_message) from e
                    raise

        # If we reach here without a final response or error, set state to complete
        agent_message.properties.state = "complete"
        return agent_message

    except ExceptionWithMessageError:
        # Re-raise ExceptionWithMessageError as is
        raise
    except Exception as e:
        error_message = str(e)
        # Special handling for code parsing errors in the exception
        if "code parsing" in error_message.lower():
            # Extract the code snippet if available
            code_snippet = ""
            if "Here is your code snippet:" in error_message:
                parts = error_message.split("Here is your code snippet:")
                if len(parts) > 1:
                    code_snippet = parts[1].strip()
            
            error_message = (
                f"Code Parsing Error:\n{code_snippet}\n\n"
                "Please ensure your code follows this exact format:\n"
                "Thoughts: Your reasoning about the task\n"
                "Code:\n```python\n# Your Python code here\n```<end_code>\n\n"
                "Common issues to check:\n"
                "1. Missing 'Thoughts:' section\n"
                "2. Incorrect code block format\n"
                "3. Missing <end_code> tag\n"
                "4. Improper indentation"
            )
        
        # Set both content and text for proper display
        agent_message.content = error_message
        agent_message.text = error_message
        
        try:
            # Clear existing error blocks to prevent duplication
            agent_message.content_blocks = [block for block in agent_message.content_blocks if block.title != "Error"]
            error_content = TextContent(
                type="text",
                text=error_message,
                duration=_calculate_duration(start_time),
                header={"title": "Error", "icon": "AlertTriangle"},
            )
            agent_message.content_blocks.append(
                ContentBlock(
                    title="Error",
                    contents=[error_content],
                )
            )
            agent_message.properties.state = "complete"
            agent_message.error = True
            await send_message_method(agent_message)
        except Exception as send_error:
            # If we can't send the error message, wrap both errors
            error_message = f"Original error: {error_message}\nFailed to send error message: {str(send_error)}"
        raise ExceptionWithMessageError(agent_message, error_message) from e
