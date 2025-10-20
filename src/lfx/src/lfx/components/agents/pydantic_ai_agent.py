"""Pydantic AI Agent Component for Langflow."""

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.agents import AgentFinish
from pydantic_ai import (
    Agent,
    AgentStreamEvent,  # stream base type
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPartDelta,
    ThinkingPartDelta,
    ToolCallPartDelta,
)
from pydantic_ai.ext.langchain import tool_from_langchain
from pydantic_ai.models.openai import OpenAIModel  # noqa: F401

from lfx.base.agents.agent import LCToolsAgentComponent
from lfx.components.helpers.current_date import CurrentDateComponent
from lfx.components.helpers.memory import MemoryComponent
from lfx.field_typing import Tool  # noqa: F401
from lfx.inputs.inputs import BoolInput, SecretStrInput
from lfx.io import HandleInput, IntInput, MessageInput, MultilineInput, Output, StrInput
from lfx.log.logger import logger
from lfx.schema.content_block import ContentBlock
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI


class PydanticAIAgentComponent(LCToolsAgentComponent):
    """Pydantic AI Agent Component.

    This component uses Pydantic AI to create an agent that can use LangChain tools.
    It supports both streaming and non-streaming modes.
    """

    display_name: str = "Pydantic AI Agent"
    description: str = "An agent powered by Pydantic AI that can use tools to complete tasks."
    documentation: str = "https://docs.langflow.org/agents"
    icon = "bot"
    beta = True
    name = "PydanticAIAgent"

    inputs = [
        SecretStrInput(
            name="openai_api_key",
            display_name="OpenAI API Key",
            info="The OpenAI API key to use for the agent.",
            required=True,
        ),
        StrInput(
            name="model_name",
            display_name="Model Name",
            info="The OpenAI model to use (e.g., gpt-4o, gpt-4-turbo, gpt-3.5-turbo).",
            value="gpt-4o",
            advanced=False,
        ),
        MessageInput(
            name="input_value",
            display_name="Input",
            info="The input provided by the user for the agent to process.",
            tool_mode=True,
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
            required=False,
            info="These are the tools that the agent can use to help with tasks.",
        ),
        MultilineInput(
            name="system_prompt",
            display_name="System Instructions",
            info="Instructions to guide the agent's behavior.",
            value="You are a helpful assistant that can use tools to answer questions and perform tasks.",
            advanced=False,
        ),
        MultilineInput(
            name="agent_description",
            display_name="Agent Description [Deprecated]",
            info="The description of the agent. This is only used when in Tool Mode.",
            advanced=True,
            value="A helpful assistant with access to the following tools:",
        ),
        BoolInput(
            name="enable_streaming",
            display_name="Enable Streaming",
            info="If true, the agent will stream events during execution.",
            value=True,
            advanced=False,
        ),
        IntInput(
            name="n_messages",
            display_name="Number of Chat History Messages",
            value=100,
            info="Number of chat history messages to retrieve.",
            advanced=True,
            show=True,
        ),
        BoolInput(
            name="add_current_date_tool",
            display_name="Current Date",
            advanced=True,
            info="If true, will add a tool to the agent that returns the current date.",
            value=True,
        ),
        IntInput(
            name="max_iterations",
            display_name="Max Iterations",
            value=15,
            advanced=True,
            info="The maximum number of attempts the agent can make to complete its task.",
        ),
        BoolInput(name="verbose", display_name="Verbose", value=True, advanced=True),
        BoolInput(
            name="enable_web_search",
            display_name="Web Search Tool",
            advanced=True,
            info="Enable web search for queries requiring up-to-date data. Supported by OpenAI, Anthropic, Google, and Groq.",
            value=False,
        ),
        BoolInput(
            name="enable_code_execution",
            display_name="Code Execution Tool",
            advanced=True,
            info="Enable code execution in a secure environment for computational tasks. Supported by OpenAI, Google, and Anthropic.",
            value=False,
        ),
        BoolInput(
            name="enable_image_generation",
            display_name="Image Generation Tool",
            advanced=True,
            info="Enable image generation capabilities. Supported by OpenAI and Google.",
            value=False,
        ),
        BoolInput(
            name="enable_url_context",
            display_name="URL Context Tool",
            advanced=True,
            info="Enable pulling URL contents into context. Currently supported by Google only.",
            value=False,
        ),
        BoolInput(
            name="enable_memory",
            display_name="Memory Tool",
            advanced=True,
            info="Enable agent memory capabilities. Supported exclusively by Anthropic.",
            value=False,
        ),
    ]

    outputs = [
        Output(name="response", display_name="Response", method="message_response"),
    ]

    async def get_agent_requirements(self):
        """Get the agent requirements for the agent."""
        # Get memory data
        self.chat_history = await self.get_memory_data()
        await logger.adebug(f"Retrieved {len(self.chat_history)} chat history messages")
        if isinstance(self.chat_history, Message):
            self.chat_history = [self.chat_history]

        # Add current date tool if enabled
        if self.add_current_date_tool:
            if not isinstance(self.tools, list):
                self.tools = []
            from langchain_core.tools import StructuredTool

            current_date_tool = (await CurrentDateComponent(**self.get_base_args()).to_toolkit()).pop(0)
            if not isinstance(current_date_tool, StructuredTool):
                msg = "CurrentDateComponent must be converted to a StructuredTool"
                raise TypeError(msg)
            self.tools.append(current_date_tool)
        return self.chat_history, self.tools

    async def run_pydantic_agent_streaming(
        self, pydantic_agent: Agent, input_text: str
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the Pydantic AI agent with streaming enabled."""
        def _coerce_tool_input(value: Any) -> dict[str, Any]:
            if value is None:
                return {}
            if isinstance(value, dict):
                return value
            if hasattr(value, "model_dump"):
                try:
                    return value.model_dump()  # type: ignore[attr-defined]
                except Exception:
                    pass
            if hasattr(value, "dict"):
                try:
                    return value.dict()  # type: ignore[attr-defined]
                except Exception:
                    pass
            if isinstance(value, (list, tuple)):
                return {"args": list(value)}
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        return parsed
                    return {"value": parsed}
                except Exception:
                    return {"value": value}
            return {"value": str(value)}
        # Yield initial chain start event
        yield {
            "event": "on_chain_start",
            "run_id": str(uuid.uuid4()),
            "name": "PydanticAIAgent",
            "data": {"input": {"input": input_text, "chat_history": []}},
        }

        try:
            # Map to track tool calls by their IDs
            tool_call_mapping: dict[str, tuple[str, str]] = {}
            aggregated_parts: list[str] = []
            aggregated_text: str = ""

            async for event in pydantic_agent.run_stream_events(input_text):
                # Strictly map on known event classes
                if isinstance(event, PartStartEvent):
                    # We don't emit UI events for generic part starts; tool starts use FunctionToolCallEvent below
                    continue

                if isinstance(event, PartDeltaEvent):
                    delta = event.delta
                    if isinstance(delta, TextPartDelta):
                        piece = delta.content_delta or ""
                        if piece:
                            aggregated_parts.append(piece)
                            aggregated_text += piece
                            yield {
                                "event": "on_chain_stream",
                                "run_id": str(uuid.uuid4()),
                                "name": "PydanticAIAgent",
                                "data": {"chunk": {"output": [aggregated_text], "cumulative": True}},
                            }
                    elif isinstance(delta, ThinkingPartDelta):
                        # Skip thinking deltas for UI text
                        pass
                    elif isinstance(delta, ToolCallPartDelta):
                        # Progressive tool-call args delta; merge shallowly and emit tool update
                        tool_call_id = getattr(delta, "tool_call_id", None) or getattr(delta, "id", None)
                        merged_args = {}
                        if tool_call_id and tool_call_id in tool_call_mapping:
                            run_id, tool_name = tool_call_mapping[tool_call_id]
                            # current args not tracked, so send delta as-is under "args_delta"
                            merged_args = {"args_delta": getattr(delta, "args_delta", {})}
                            yield {
                                "event": "on_tool_update",
                                "run_id": run_id,
                                "name": tool_name,
                                "data": {"input": merged_args},
                            }
                    continue

                if isinstance(event, FunctionToolCallEvent):
                    part = event.part
                    tool_name = getattr(part, "tool_name", "unknown_tool")
                    tool_call_id = getattr(part, "tool_call_id", None)
                    raw_args = getattr(part, "args", {})
                    args = _coerce_tool_input(raw_args)
                    if tool_call_id:
                        run_id = str(uuid.uuid4())
                        tool_call_mapping[tool_call_id] = (run_id, tool_name)
                        yield {
                            "event": "on_tool_start",
                            "run_id": run_id,
                            "name": tool_name,
                            "data": {"input": args},
                        }
                    continue

                if isinstance(event, FunctionToolResultEvent):
                    tool_call_id = getattr(event, "tool_call_id", None)
                    if tool_call_id and tool_call_id in tool_call_mapping:
                        run_id, tool_name = tool_call_mapping[tool_call_id]
                        # result.content is expected; fallback to str(event.result)
                        result_content = getattr(event.result, "content", None)
                        output_text = result_content if isinstance(result_content, str) else str(event.result)
                        yield {
                            "event": "on_tool_end",
                            "run_id": run_id,
                            "name": tool_name,
                            "data": {"output": output_text},
                        }
                        del tool_call_mapping[tool_call_id]
                    continue

                if isinstance(event, FinalResultEvent):
                    final_output = aggregated_text or "".join(aggregated_parts)
                    yield {
                        "event": "on_chain_end",
                        "run_id": str(uuid.uuid4()),
                        "name": "PydanticAIAgent",
                        "data": {"output": AgentFinish(return_values={"output": final_output}, log="")},
                    }
                    continue

                # Fallback: some older versions may emit AgentRunResultEvent with .result
                if type(event).__name__ == "AgentRunResultEvent":
                    result_output = getattr(event.result, "output", None)
                    if result_output is not None and hasattr(result_output, "__aiter__"):
                        try:
                            async for out in result_output:  # type: ignore[func-returns-value]
                                if out is None:
                                    continue
                                piece = getattr(out, "data", out)
                                if not isinstance(piece, str):
                                    piece = str(piece)
                                aggregated_parts.append(piece)
                                aggregated_text += piece
                                yield {
                                    "event": "on_chain_stream",
                                    "run_id": str(uuid.uuid4()),
                                    "name": "PydanticAIAgent",
                                    "data": {"chunk": {"output": [aggregated_text], "cumulative": True}},
                                }
                        except Exception as stream_err:
                            yield {
                                "event": "on_chain_error",
                                "run_id": str(uuid.uuid4()),
                                "name": "PydanticAIAgent",
                                "data": {"error": str(stream_err)},
                            }
                            raise
                        final_output = aggregated_text or "".join(aggregated_parts)
                    else:
                        if result_output is not None and hasattr(result_output, "data"):
                            final_output = str(result_output.data)
                        else:
                            final_output = aggregated_text or ("".join(aggregated_parts) if aggregated_parts else str(result_output))
                    yield {
                        "event": "on_chain_end",
                        "run_id": str(uuid.uuid4()),
                        "name": "PydanticAIAgent",
                        "data": {"output": AgentFinish(return_values={"output": final_output}, log="")},
                    }
        # INSERT_YOUR_CODE
            import asyncio
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Error in Pydantic AI agent streaming: {e}")
            yield {
                "event": "on_chain_error",
                "run_id": str(uuid.uuid4()),
                "name": "PydanticAIAgent",
                "data": {"error": str(e)},
            }
            raise

    async def run_pydantic_agent_non_streaming(self, pydantic_agent: Agent, input_text: str) -> str:
        """Run the Pydantic AI agent without streaming."""
        try:
            result = await pydantic_agent.run(input_text)
            # Extract the text from the result
            if hasattr(result, "data"):
                return str(result.data)
            return str(result)
        except Exception as e:
            logger.error(f"Error in Pydantic AI agent execution: {e}")
            raise

    async def message_response(self) -> Message:
        """Generate a message response using the Pydantic AI agent."""
        logger.info("[PydanticAIAgent] Starting agent run for message_response.")

        # Validate input
        if not self.input_value or not str(self.input_value).strip():
            msg = "Message cannot be empty. Please provide a valid message."
            raise ValueError(msg)

        # Validate OpenAI API key
        if not self.openai_api_key:
            msg = "OpenAI API key is required. Please provide a valid API key."
            raise ValueError(msg)

        try:
            self.chat_history, self.tools = await self.get_agent_requirements()

            # Create OpenAI model for Pydantic AI
            from pydantic_ai.models.openai import OpenAIResponsesModel
            from pydantic_ai.providers.openai import OpenAIProvider

            provider = OpenAIProvider(api_key=self.openai_api_key)
            model = OpenAIResponsesModel(self.model_name, provider=provider)

            # Convert LangChain tools to Pydantic AI tools before creating agent
            pydantic_tools = []
            if self.tools:
                for tool in self.tools:
                    try:
                        pydantic_tool = tool_from_langchain(tool)
                        pydantic_tools.append(pydantic_tool)
                        logger.info(f"[PydanticAIAgent] Converted tool: {tool.name}")
                    except Exception as e:
                        logger.warning(f"[PydanticAIAgent] Failed to convert tool {tool.name}: {e}")

            # Configure built-in tools based on boolean flags
            builtin_tools = []
            if self.enable_web_search:
                from pydantic_ai import WebSearchTool
                builtin_tools.append(WebSearchTool())
                logger.info("[PydanticAIAgent] Enabled Web Search Tool")

            if self.enable_code_execution:
                from pydantic_ai import CodeExecutionTool
                builtin_tools.append(CodeExecutionTool())
                logger.info("[PydanticAIAgent] Enabled Code Execution Tool")

            if self.enable_image_generation:
                from pydantic_ai import ImageGenerationTool
                builtin_tools.append(ImageGenerationTool())
                logger.info("[PydanticAIAgent] Enabled Image Generation Tool")

            if self.enable_url_context:
                from pydantic_ai import UrlContextTool
                builtin_tools.append(UrlContextTool())
                logger.info("[PydanticAIAgent] Enabled URL Context Tool")

            if self.enable_memory:
                from pydantic_ai import MemoryTool
                builtin_tools.append(MemoryTool())
                logger.info("[PydanticAIAgent] Enabled Memory Tool")

            # Create Pydantic AI agent with tools and built-in tools
            pydantic_agent = Agent(
                model=model,
                instructions=self.system_prompt,
                tools=pydantic_tools if pydantic_tools else None,
                builtin_tools=builtin_tools if builtin_tools else None,
            )

            # Get input text
            input_text = self.input_value.text if hasattr(self.input_value, "text") else str(self.input_value)

            # Run agent based on streaming mode
            if self.enable_streaming:
                # Create agent message for event processing
                agent_message = Message(
                    sender=MESSAGE_SENDER_AI,
                    sender_name="Pydantic AI Agent",
                    properties={"icon": "Bot", "state": "partial"},
                    content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
                    session_id=self.graph.session_id if hasattr(self, "graph") else str(uuid.uuid4()),
                )

                # Process events using the existing event processing system
                from typing import cast

                from lfx.base.agents.events import process_agent_events
                from lfx.schema.log import SendMessageFunctionType

                event_iterator = self.run_pydantic_agent_streaming(pydantic_agent, input_text)
                result = await process_agent_events(
                    event_iterator, agent_message, cast(SendMessageFunctionType, self.send_message)
                )

                logger.info("[PydanticAIAgent] Agent run finished successfully with streaming.")
                return result
            else:
                # Non-streaming mode: just return text output
                output_text = await self.run_pydantic_agent_non_streaming(pydantic_agent, input_text)

                # Create a simple message without content blocks
                result_message = Message(
                    sender=MESSAGE_SENDER_AI,
                    sender_name="Pydantic AI Agent",
                    text=output_text,
                    properties={"icon": "Bot", "state": "complete"},
                    session_id=self.graph.session_id if hasattr(self, "graph") else str(uuid.uuid4()),
                )

                # Send the message
                result_message = await self.send_message(result_message)

                logger.info("[PydanticAIAgent] Agent run finished successfully without streaming.")
                return result_message

        except Exception as e:
            logger.error(f"[PydanticAIAgent] Error in message_response: {e}")
            raise

    async def get_memory_data(self):
        """Retrieve chat history messages."""
        messages = (
            await MemoryComponent(**self.get_base_args())
            .set(
                session_id=self.graph.session_id,
                order="Ascending",
                n_messages=self.n_messages,
            )
            .retrieve_messages()
        )
        return [
            message for message in messages if getattr(message, "id", None) != getattr(self.input_value, "id", None)
        ]
