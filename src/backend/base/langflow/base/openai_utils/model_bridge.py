import json
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
        messages = self._convert_to_langchain_messages(system_instructions, input)
        lc_model = self._configure_tools(self.langchain_model, tools)
        response = await lc_model.ainvoke(messages)
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
        messages = self._convert_to_langchain_messages(system_instructions, input)
        lc_model = self._configure_tools(self.langchain_model, tools)
        stream = lc_model.astream(messages)
        async for chunk in stream:
            yield self._convert_to_stream_event(chunk)

    def _configure_tools(self, lc_model, tools):
        """Configure tools for LangChain model if needed."""
        if tools and hasattr(lc_model, "bind_tools"):
            lc_tools = self._convert_to_langchain_tools(tools)
            return lc_model.bind_tools(lc_tools)
        return lc_model

    def _convert_to_langchain_tools(self, tools: list[Tool]) -> list[dict]:
        """Convert OpenAI Agents tools to LangChain-compatible format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": self._extract_tool_parameters(tool),
                },
            }
            for tool in tools
        ]

    def _extract_tool_parameters(self, tool):
        """Extract parameters from the tool's schema if available."""
        if hasattr(tool, "parameter_schema") and tool.parameter_schema:
            return {
                "type": "object",
                "properties": tool.parameter_schema.properties,
                "required": getattr(tool.parameter_schema, "required", []),
            }
        return {}

    def _convert_to_langchain_messages(self, system_instructions, input):
        """Convert OpenAI Agents input format to LangChain messages."""
        messages = [SystemMessage(content=system_instructions)] if system_instructions else []
        if isinstance(input, str):
            messages.append(HumanMessage(content=input))
        else:
            for item in input:
                messages.append(self._create_message_from_item(item))
        return messages

    def _create_message_from_item(self, item):
        """Create a LangChain message from an input item."""
        role = item.get("role")
        content = item.get("content", "")
        if role == "user":
            return HumanMessage(content=content)
        elif role == "assistant":
            return AIMessage(content=content)
        elif role == "tool":
            return ToolMessage(content=content, tool_call_id=item.get("tool_call_id", ""))
        return None

    def _convert_to_model_response(self, langchain_response):
        """Convert LangChain response to OpenAI Agents ModelResponse format."""
        content, tool_calls = self._extract_response_content_and_tools(langchain_response)
        output_content = self._create_output_content(content, tool_calls)
        message = ResponseOutputMessage(
            id=str(uuid.uuid4()),
            content=[output_content[0]],  # Only include the text content
            role="assistant",
            status="completed",
            type="message",
        )
        usage = Usage(input_tokens=0, output_tokens=0, total_tokens=0)
        return ModelResponse(output=[message], usage=usage, referenceable_id=None)

    def _extract_response_content_and_tools(self, langchain_response):
        """Extract content and tool calls from LangChain response."""
        content = ""
        tool_calls = []
        if isinstance(langchain_response, AIMessage):
            content = langchain_response.content or ""
            tool_calls = self._extract_tool_calls(langchain_response)
        elif isinstance(langchain_response, dict):
            content = langchain_response.get("content", "")
            tool_calls = langchain_response.get("tool_calls", [])
        elif isinstance(langchain_response, str):
            content = langchain_response
        return content, tool_calls

    def _extract_tool_calls(self, langchain_response):
        """Extract tool calls from LangChain response."""
        tool_calls = []
        if hasattr(langchain_response, "additional_kwargs"):
            tool_calls.extend(self._extract_tool_calls_from_kwargs(langchain_response.additional_kwargs))
        if hasattr(langchain_response, "tool_calls"):
            tool_calls.extend(langchain_response.tool_calls)
        logger.info(f"Extracted tool calls: {tool_calls}")
        return tool_calls

    def _extract_tool_calls_from_kwargs(self, additional_kwargs):
        """Extract tool calls from additional_kwargs."""
        tool_calls = []
        if "function_call" in additional_kwargs:
            function_call = additional_kwargs["function_call"]
            tool_calls.append({"name": function_call.get("name", "unknown_tool"), "args": function_call.get("arguments", "{}")})
        elif "tool_calls" in additional_kwargs:
            for tool_call in additional_kwargs["tool_calls"]:
                if "function" in tool_call:
                    function_info = tool_call["function"]
                    tool_calls.append({"name": function_info.get("name", "unknown_tool"), "args": function_info.get("arguments", "{}")})
        return tool_calls

    def _create_output_content(self, content, tool_calls):
        """Create output content for the response."""
        output_content = []
        if content:
            output_content.append(ResponseOutputText(text=content, annotations=[], type="output_text"))
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "unknown_tool")
            tool_args = tool_call.get("args", {})
            args_str = tool_args if isinstance(tool_args, str) else json.dumps(tool_args)
            tool_call_output = ResponseFunctionToolCall(
                id=str(uuid.uuid4()),
                call_id=str(uuid.uuid4()),
                name=tool_name,
                arguments=args_str,
                type="function_call",
                status="completed",
            )
            output_content.append(tool_call_output)
            logger.info(f"Executing tool call: {tool_name} with args: {args_str}")
        if not content and tool_calls:
            default_text = f"I'll use the {tool_calls[0]['name']} tool to help answer your question."
            output_content.insert(0, ResponseOutputText(text=default_text, annotations=[], type="output_text"))
        return output_content

    def _convert_to_stream_event(self, langchain_chunk) -> RawResponsesStreamEvent:
        """Convert LangChain streaming chunk to OpenAI Agents stream event format."""
        stream_event = {"type": "content_block_delta", "delta": {"text": langchain_chunk.content}}
        return RawResponsesStreamEvent(data=stream_event)


def example_basic():
    import os

    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, api_key=os.getenv("OPENAI_API_KEY_TEST"))

    # Create the bridge to use with OpenAI Agents
    langchain_model_bridge = LangChainModelBridge(llm)

    import asyncio

    from agents import Agent, Runner

    spanish_agent = Agent(name="Spanish agent", instructions="You only speak Spanish.", model=langchain_model_bridge)

    english_agent = Agent(name="English agent", instructions="You only speak English", model=langchain_model_bridge)

    triage_agent = Agent(
        name="Triage agent",
        instructions="Handoff to the appropriate agent based on the language of the request.",
        handoffs=[spanish_agent, english_agent],
        model=langchain_model_bridge,
    )

    result = asyncio.run(Runner.run(triage_agent, input="hi how are you?"))
    print(result.final_output)


async def example_with_tools():
    import os

    from agents import Agent, Runner, function_tool
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    # Create a function tool for testing
    from langchain_core.tools import tool
    @tool
    def get_weather(city: str) -> str:
        """Tool to get the weather in a city."""
        result = f"The weather in {city} is sunny."
        logger.info(f"Tool called with city={city}, returning: {result}")
        return result

    # Try to use OpenAI if API key is available, otherwise use a fake LLM
    api_key = os.getenv("OPENAI_API_KEY_TEST")

    # Use ChatOpenAI if API key is available
    from langchain_openai import ChatOpenAI

    logger.info("Using ChatOpenAI with API key")
    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, api_key=api_key)

    # Create the bridge to use with OpenAI Agents
    langchain_model_bridge = LangChainModelBridge(llm)

    # Create an agent with the model
    agent = Agent(
        name="Weather Agent",
        instructions="You are a helpful agent that can check the weather.",
        tools=[get_weather],
        model=langchain_model_bridge,
    )

    # Run the agent
    logger.info("Running agent...")
    result = await Runner.run(agent, input="What's the weather in Tokyo?")
    logger.info(f"Result: {result}")
    logger.info(f"Final output: {result.final_output}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_with_tools())
    # example_basic()
