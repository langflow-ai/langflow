import asyncio
import os
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from agents import (
    Agent,
    AgentOutputSchema,
    Handoff,
    Model,
    ModelResponse,
    ModelSettings,
    ModelTracing,
    Runner,
    Tool,
    function_tool,
    set_tracing_disabled,
)
from agents.items import ResponseOutputMessage, ResponseOutputText, TResponseStreamEvent
from agents.stream_events import RawResponsesStreamEvent
from agents.usage import Usage
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import Tool as LCTool
from langchain_openai import ChatOpenAI

# Use environment variables or set them in your code
MODEL_NAME = os.getenv("EXAMPLE_MODEL_NAME") or "gpt-4o-mini"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY_TEST")

# Disable tracing if needed (or set up LangSmith/Langfuse tracing as desired)
set_tracing_disabled(disabled=True)


class LangChainModelBridge(Model):
    """Bridge class to use LangChain models with OpenAI Agents framework."""

    def __init__(self, langchain_model):
        """Initialize with a LangChain model."""
        self.langchain_model = langchain_model

    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[Any],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchema | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
    ) -> ModelResponse:
        """Get a response from the LangChain model."""
        # Convert OpenAI Agents input format to LangChain messages
        messages = self._convert_to_langchain_messages(system_instructions, input)

        # Handle tools if needed
        lc_model = self.langchain_model
        if tools and hasattr(lc_model, "bind_tools"):
            # Convert OpenAI Agents tools to LangChain tools
            lc_tools = self._convert_to_langchain_tools(tools)
            # Configure tools for LangChain
            lc_model = lc_model.bind_tools(lc_tools)

        # Call the LangChain model
        response = await lc_model.ainvoke(messages)

        # Convert LangChain response to OpenAI Agents ModelResponse format
        return self._convert_to_model_response(response)

    async def stream_response(
        self,
        system_instructions: str | None,
        input: str | list[Any],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchema | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
    ) -> AsyncIterator[RawResponsesStreamEvent]:
        """Stream a response from the LangChain model."""
        # Convert OpenAI Agents input format to LangChain messages
        messages = self._convert_to_langchain_messages(system_instructions, input)

        # Handle tools if needed
        lc_model = self.langchain_model
        if tools and hasattr(lc_model, "bind_tools"):
            # Convert OpenAI Agents tools to LangChain tools
            lc_tools = self._convert_to_langchain_tools(tools)
            # Configure tools for LangChain
            lc_model = lc_model.bind_tools(lc_tools)

        # Stream from the LangChain model
        stream = lc_model.astream(messages)

        # Convert LangChain streaming chunks to OpenAI Agents format
        async for chunk in stream:
            yield self._convert_to_stream_event(chunk)

    def _convert_to_langchain_tools(self, tools: list[Tool]) -> list[dict]:
        """Convert OpenAI Agents tools to LangChain-compatible format."""
        lc_tools = []

        for tool in tools:
            # Extract tool information
            name = tool.name
            description = tool.description
            parameters = {}

            # Extract parameters from the tool's schema if available
            if hasattr(tool, "parameter_schema") and tool.parameter_schema:
                if hasattr(tool.parameter_schema, "properties"):
                    parameters = {
                        "type": "object",
                        "properties": tool.parameter_schema.properties,
                        "required": tool.parameter_schema.required
                        if hasattr(tool.parameter_schema, "required")
                        else [],
                    }

            # Create OpenAI tool format that LangChain expects
            lc_tool = {
                "type": "function",
                "function": {"name": name, "description": description, "parameters": parameters},
            }
            lc_tools.append(lc_tool)

        return lc_tools

    def _convert_to_langchain_messages(self, system_instructions, input):
        """Convert OpenAI Agents input format to LangChain messages."""
        messages = []

        # Add system message if provided
        if system_instructions:
            messages.append(SystemMessage(content=system_instructions))

        # Handle string input (simple human message)
        if isinstance(input, str):
            messages.append(HumanMessage(content=input))
        # Handle list of input items
        else:
            for item in input:
                if item.get("role") == "user":
                    messages.append(HumanMessage(content=item.get("content", "")))
                elif item.get("role") == "assistant":
                    messages.append(AIMessage(content=item.get("content", "")))
                elif item.get("role") == "tool":
                    messages.append(
                        ToolMessage(content=item.get("content", ""), tool_call_id=item.get("tool_call_id", ""))
                    )
                # Add other message types as needed

        return messages

    def _convert_to_model_response(self, langchain_response):
        """Convert LangChain response to OpenAI Agents ModelResponse format."""
        # Create a ResponseOutputText object with the content
        text_content = ResponseOutputText(
            text=langchain_response.content,
            annotations=[],  # Empty list of annotations
            type="output_text",  # Required type field
        )

        # Create a ResponseOutputMessage object with all required fields
        message = ResponseOutputMessage(
            id=str(uuid.uuid4()),  # Generate a unique ID
            content=[text_content],
            role="assistant",
            status="completed",  # One of: "in_progress", "completed", "incomplete"
            type="message",  # Required type field
        )

        # Create a simple usage object
        # In a real implementation, you might want to extract token usage from langchain_response.response_metadata
        usage = Usage(input_tokens=0, output_tokens=0, total_tokens=0)

        # Create and return the ModelResponse
        return ModelResponse(output=[message], usage=usage, referenceable_id=None)

    def _convert_to_stream_event(self, langchain_chunk) -> RawResponsesStreamEvent:
        """Convert LangChain streaming chunk to OpenAI Agents stream event format."""
        # Create a TResponseStreamEvent (the raw event data expected by RawResponsesStreamEvent)
        stream_event: dict[str, Any] = {
            "type": "content_block_delta",
            "delta": {"text": langchain_chunk.content},
        }

        # Wrap it in a RawResponsesStreamEvent as expected by the OpenAI Agents framework
        return RawResponsesStreamEvent(data=stream_event)




# def example_basic():
#     llm = ChatOpenAI(model_name=MODEL_NAME, temperature=0, api_key=OPENAI_API_KEY)

#     # Create the bridge to use with OpenAI Agents
#     langchain_model_bridge = LangChainModelBridge(llm)

#     import asyncio

#     from agents import Agent, Runner

#     spanish_agent = Agent(name="Spanish agent", instructions="You only speak Spanish.", model=langchain_model_bridge)

#     english_agent = Agent(name="English agent", instructions="You only speak English", model=langchain_model_bridge)

#     triage_agent = Agent(
#         name="Triage agent",
#         instructions="Handoff to the appropriate agent based on the language of the request.",
#         handoffs=[spanish_agent, english_agent],
#         model=langchain_model_bridge,
#     )

#     result = asyncio.run(Runner.run(triage_agent, input="hi how are you?"))
#     print(result.final_output)

# if __name__ == "__main__":
#     example_basic()
