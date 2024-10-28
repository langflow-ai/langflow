
from langflow.components.agents.tool_calling import ToolCallingAgentComponent
from langflow.components.inputs.chat import ChatInput
from langflow.components.models.ollama import ChatOllamaComponent
from langflow.components.models.openai import OpenAIModelComponent
from langflow.components.outputs import ChatOutput
from langflow.graph.graph.base import Graph
from langflow.graph.state.model import create_state_model
from langflow.io import (
    DataInput,
    DropdownInput,
    FloatInput,
    HandleInput,
    MessageTextInput,
    Output,
    SecretStrInput,
    StrInput,
)
from langflow.schema.message import Message


class SimpleAgentComponent(ToolCallingAgentComponent):
    display_name: str = "Simple Agent"
    description: str = "Agent that uses tools"
    icon = "workflow"
    beta = True
    name = "SimpleAgent"

    inputs = [
        HandleInput(
            name="tools", display_name="Tools", input_types=["Tool", "BaseTool", "StructuredTool"], is_list=True
        ),
        MessageTextInput(name="input_value", display_name="Input"),
        HandleInput(name="llm", display_name="Language Model", input_types=["LanguageModel"], required=False),
        DataInput(name="chat_history", display_name="Chat History", is_list=True, advanced=True),
        StrInput(
            name="openai_api_base",
            display_name="OpenAI API Base",
            advanced=True,
            info="The base URL of the OpenAI API. "
            "Defaults to https://api.openai.com/v1. "
            "You can change this to use other APIs like JinaChat, LocalAI and Prem.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="OpenAI API Key",
            info="The OpenAI API Key to use for the OpenAI model.",
            advanced=False,
            value="OPENAI_API_KEY",
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.1),
        DropdownInput(name="llm_type", display_name="Language Model", options=["OpenAI","Ollama"], value="OpenAI"),
    ]
    outputs = [Output(name="response", display_name="Response", method="get_response")]

    async def get_response(self) -> Message:
        # Chat input initialization

        # Default OpenAI Model Component
        llm = OpenAIModelComponent().set(
            openai_api_base=self.openai_api_base,
            api_key=self.api_key,
            temperature=self.temperature,
        ).build_model()
        llm_model = self.llm if self.llm else llm

        agent = ToolCallingAgentComponent().set(
            llm=llm_model, tools=[self.tools], chat_history=self.chat_history, input_value=self.input_value
        )
        # Chat output
        # chat_output = ChatOutput().set(input_value=agent.message_response)
        # output_model = create_state_model("SimpleAgentOutput", output=chat_output.message_response)

        # # Build the graph
        # graph = Graph(chat_input, chat_output)
        # async for result in graph.async_start():
        #     print(result)
        #     logger.info(result)

        return await agent.message_response()
    def get_llm(self):
        if self.llm_type == "OpenAI":
            return OpenAIModelComponent().set(
                openai_api_base=self.openai_api_base, api_key=self.api_key, temperature=self.temperature
            ).build_model()
        if self.llm_type == "Ollama":
            return ChatOllamaComponent().set(
                base_url=self.ollama_base_url, temperature=self.temperature
            ).build_model()
        return None
