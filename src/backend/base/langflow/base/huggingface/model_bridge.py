# Import LangChain base
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolCall
from langchain_core.tools import BaseTool

# Import Hugging Face Model base
from smolagents import Model, Tool
from smolagents.models import ChatMessage, ChatMessageToolCall, ChatMessageToolCallDefinition


def _lc_tool_call_to_hf_tool_call(tool_call: ToolCall) -> ChatMessageToolCall:
    """Convert a LangChain ToolCall to a Hugging Face ChatMessageToolCall.

    Args:
        tool_call (ToolCall): LangChain tool call to convert

    Returns:
        ChatMessageToolCall: Equivalent Hugging Face tool call
    """
    return ChatMessageToolCall(
        function=ChatMessageToolCallDefinition(name=tool_call.name, arguments=tool_call.args),
        id=tool_call.id,
    )


def _hf_tool_to_lc_tool(tool) -> BaseTool:
    """Convert a Hugging Face Tool to a LangChain BaseTool.

    Args:
        tool (Tool): Hugging Face tool to convert

    Returns:
        BaseTool: Equivalent LangChain tool
    """
    if not hasattr(tool, "langchain_tool"):
        msg = "Hugging Face Tool does not have a langchain_tool attribute"
        raise ValueError(msg)
    return tool.langchain_tool


class LangChainHFModel(Model):
    """A class bridging Hugging Face's `Model` interface with a LangChain `BaseChatModel`.

    This adapter allows using any LangChain chat model with the Hugging Face interface.
    It handles conversion of message formats and tool calls between the two frameworks.

    Usage:
       >>> lc_model = LangChainChatModel(...)  # any BaseChatModel
       >>> hf_model = LangChainHFModel(lc_model)
       >>> hf_model(messages=[{"role": "user", "content": "Hello!"}])
    """

    def __init__(self, chat_model: BaseChatModel, **kwargs):
        """Initialize the bridge model.

        Args:
            chat_model (BaseChatModel): LangChain chat model to wrap
            **kwargs: Additional arguments passed to Model.__init__
        """
        super().__init__(**kwargs)
        self.chat_model = chat_model

    def __call__(
        self,
        messages: list[dict[str, str]],
        stop_sequences: list[str] | None = None,
        grammar: str | None = None,
        tools_to_call_from: list[Tool] | None = None,
        **kwargs,
    ) -> ChatMessage:
        """Process messages through the LangChain model and return Hugging Face format.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            stop_sequences: Optional list of strings to stop generation
            grammar: Optional grammar specification (not used)
            tools_to_call_from: Optional list of available tools (not used)
            **kwargs: Additional arguments passed to the LangChain model

        Returns:
            ChatMessage: Response in Hugging Face format
        """
        if grammar:
            msg = "Grammar is not yet supported."
            raise ValueError(msg)

        # Convert HF messages to LangChain messages
        lc_messages = []
        for m in messages:
            role = m["role"]
            content = m["content"]
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                # Default any unknown role to "user"
                lc_messages.append(HumanMessage(content=content))

        # Convert tools to LangChain tools
        if tools_to_call_from:
            tools_to_call_from = [_hf_tool_to_lc_tool(tool) for tool in tools_to_call_from]

        model = self.chat_model.bind_tools(tools_to_call_from) if tools_to_call_from else self.chat_model

        # Call the LangChain model
        result_msg: AIMessage = model.invoke(lc_messages, stop=stop_sequences, **kwargs)

        # Convert the AIMessage into an HF ChatMessage
        return ChatMessage(
            role="assistant",
            content=result_msg.content or "",
            tool_calls=[_lc_tool_call_to_hf_tool_call(tool_call) for tool_call in result_msg.tool_calls],
        )


# How to use
# if __name__ == "__main__":
#     from langchain_community.tools import DuckDuckGoSearchRun
#     from langchain_openai import ChatOpenAI
#     from rich import rprint
#     from smolagents import CodeAgent

#     # Example usage
#     model = LangChainHFModel(chat_model=ChatOpenAI(model="gpt-4o-mini"))
#     search_tool = DuckDuckGoSearchRun()
#     hf_tool = Tool.from_langchain(search_tool)

#     code_agent = CodeAgent(
#         model=model,
#         tools=[hf_tool],
#     )
#     rprint(code_agent.run("Search for Langflow on DuckDuckGo and return the first result"))
