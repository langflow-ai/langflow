from langchain.agents import create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate

from langflow.base.agents.agent import LCToolsAgentComponent
from langflow.inputs import MessageTextInput
from langflow.inputs.inputs import DataInput, HandleInput
from langflow.schema import Data


class ToolCallingAgentComponent(LCToolsAgentComponent):
    display_name: str = "Tool Calling Agent"
    description: str = "An agent designed to utilize various tools seamlessly within workflows."
    icon = "LangChain"
    beta = True
    name = "ToolCallingAgent"

    inputs = [
        *LCToolsAgentComponent._base_inputs,
        HandleInput(name="llm", display_name="Language Model", input_types=["LanguageModel"], required=True),
        MessageTextInput(
            name="system_prompt",
            display_name="System Prompt",
            info="Initial instructions and context provided to guide the agent's behavior.",
            value="You are a helpful assistant that can use tools to answer questions and perform tasks.",
        ),
        MessageTextInput(
            name="input_value",
            display_name="Input",
            info="The input provided by the user for the agent to process.",
        ),
        DataInput(name="chat_history", display_name="Chat Memory", is_list=True, advanced=True),
    ]

    def get_chat_history_data(self) -> list[Data] | None:
        return self.chat_history

    def create_agent_runnable(self):
        messages = [
            ("system", self.system_prompt),
            ("placeholder", "{chat_history}"),
            ("human", self.input_value),
            ("placeholder", "{agent_scratchpad}"),
        ]
        prompt = ChatPromptTemplate.from_messages(messages)
        try:
            return create_tool_calling_agent(self.llm, self.tools or [], prompt)
        except NotImplementedError as e:
            message = f"{self.display_name} does not support tool calling. Please try using a compatible model."
            raise NotImplementedError(message) from e
