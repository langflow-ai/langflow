import uuid
from collections.abc import AsyncIterator
from typing import Any

from agents import (
    AgentOutputSchema,
    Handoff,
    Model,
    ModelResponse,
    ModelSettings,
    ModelTracing,
    Tool,
    set_tracing_disabled,
)
from agents.items import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from agents.stream_events import RawResponsesStreamEvent
from agents.usage import Usage
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from langflow.logging import logger

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
            if (
                hasattr(tool, "parameter_schema")
                and tool.parameter_schema
                and hasattr(tool.parameter_schema, "properties")
            ):
                parameters = {
                    "type": "object",
                    "properties": tool.parameter_schema.properties,
                    "required": tool.parameter_schema.required if hasattr(tool.parameter_schema, "required") else [],
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
        # Extract content from the LangChain response
        content = ""
        tool_calls = []

        # Handle AIMessage response
        if isinstance(langchain_response, AIMessage):
            # Extract content
            content = langchain_response.content if langchain_response.content else ""

            # Check for function calls in additional_kwargs
            if hasattr(langchain_response, "additional_kwargs") and langchain_response.additional_kwargs:
                # Handle function_call in additional_kwargs (OpenAI format)
                if "function_call" in langchain_response.additional_kwargs:
                    function_call = langchain_response.additional_kwargs["function_call"]
                    tool_calls.append(
                        {
                            "name": function_call.get("name", "unknown_tool"),
                            "args": function_call.get("arguments", "{}"),
                        }
                    )

                # Handle tool_calls in additional_kwargs (newer OpenAI format)
                elif "tool_calls" in langchain_response.additional_kwargs:
                    for tool_call in langchain_response.additional_kwargs["tool_calls"]:
                        if "function" in tool_call:
                            function_info = tool_call["function"]
                            tool_calls.append(
                                {
                                    "name": function_info.get("name", "unknown_tool"),
                                    "args": function_info.get("arguments", "{}"),
                                }
                            )

            # Check for tool_calls attribute (LangChain format)
            if hasattr(langchain_response, "tool_calls") and langchain_response.tool_calls:
                for tool_call in langchain_response.tool_calls:
                    if isinstance(tool_call, dict):
                        tool_calls.append(
                            {"name": tool_call.get("name", "unknown_tool"), "args": tool_call.get("args", {})}
                        )

        # Handle dict response with tool_calls
        elif isinstance(langchain_response, dict):
            if langchain_response.get("content"):
                content = langchain_response["content"]

            if langchain_response.get("tool_calls"):
                tool_calls = langchain_response["tool_calls"]

            # Check for function_call in the dict (OpenAI format)
            if langchain_response.get("function_call"):
                function_call = langchain_response["function_call"]
                tool_calls.append(
                    {"name": function_call.get("name", "unknown_tool"), "args": function_call.get("arguments", "{}")}
                )

        # Handle string response
        elif isinstance(langchain_response, str):
            content = langchain_response

        # Handle other response types
        else:
            if hasattr(langchain_response, "content"):
                content = langchain_response.content if langchain_response.content else ""

            if hasattr(langchain_response, "tool_calls"):
                tool_calls = langchain_response.tool_calls

        # Process tool calls if present
        if tool_calls:
            # Create a response with tool calls
            output_content = []

            # Add text content if available
            if content:
                text_content = ResponseOutputText(
                    text=content,
                    annotations=[],
                    type="output_text",
                )
                output_content.append(text_content)

            # Add tool calls
            for tool_call in tool_calls:
                tool_name = tool_call.get("name", "unknown_tool")

                # Handle both dict and string arguments
                tool_args = tool_call.get("args", {})
                if isinstance(tool_args, str):
                    args_str = tool_args
                else:
                    # Convert args dict to JSON string
                    import json

                    args_str = json.dumps(tool_args)

                call_id = str(uuid.uuid4())

                tool_call_output = ResponseFunctionToolCall(
                    id=str(uuid.uuid4()),
                    call_id=call_id,
                    name=tool_name,
                    arguments=args_str,
                    type="function_call",
                    status="completed",
                )
                output_content.append(tool_call_output)

                # If content is empty but we have tool calls, add a default message
                if not content and not any(isinstance(item, ResponseOutputText) for item in output_content):
                    default_text = f"I'll use the {tool_name} tool to help answer your question."
                    text_content = ResponseOutputText(
                        text=default_text,
                        annotations=[],
                        type="output_text",
                    )
                    output_content.insert(0, text_content)  # Insert at beginning

            # Create message with tool calls
            message = ResponseOutputMessage(
                id=str(uuid.uuid4()),
                content=[output_content[0]],  # Only include the text content
                role="assistant",
                status="completed",
                type="message",
            )
        else:
            # Create a simple text response
            text_content = ResponseOutputText(
                text=content,
                annotations=[],
                type="output_text",
            )

            message = ResponseOutputMessage(
                id=str(uuid.uuid4()),
                content=[text_content],
                role="assistant",
                status="completed",
                type="message",
            )

        # Create a simple usage object
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
#     import os

#     from langchain_openai import ChatOpenAI

#     llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, api_key=os.getenv("OPENAI_API_KEY_TEST"))

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


# async def example_with_tools():
#     import os

#     from agents import Agent, Runner, function_tool
#     from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

#     # Create a function tool for testing
#     @function_tool
#     def get_weather(city: str) -> str:
#         result = f"The weather in {city} is sunny."
#         logger.info(f"Tool called with city={city}, returning: {result}")
#         return result

#     # Try to use OpenAI if API key is available, otherwise use a fake LLM
#     api_key = os.getenv("OPENAI_API_KEY_TEST")

#     # Use ChatOpenAI if API key is available
#     from langchain_openai import ChatOpenAI

#     logger.info("Using ChatOpenAI with API key")
#     llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, api_key=api_key)

#     # Create the bridge to use with OpenAI Agents
#     langchain_model_bridge = LangChainModelBridge(llm)

#     # Create an agent with the model
#     agent = Agent(
#         name="Weather Agent",
#         instructions="You are a helpful agent that can check the weather.",
#         tools=[get_weather],
#         model=langchain_model_bridge,
#     )

#     # Run the agent
#     logger.info("Running agent...")
#     result = await Runner.run(agent, input="What's the weather in Tokyo?")
#     logger.info(f"Result: {result}")
#     logger.info(f"Final output: {result.final_output}")


# if __name__ == "__main__":
#     import asyncio

#     # asyncio.run(example_with_tools())
#     # example_basic()
