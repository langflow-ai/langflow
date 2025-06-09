from langchain.agents import create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, PromptTemplate

from langflow.base.agents.agent import LCToolsAgentComponent
from langflow.inputs.inputs import (
    DataInput,
    HandleInput,
    MultilineInput,
)
from langflow.schema.data import Data


class OpenAIToolsAgentComponent(LCToolsAgentComponent):
    display_name: str = "OpenAI Tools Agent"
    description: str = "Agent that uses tools via openai-tools."
    icon = "LangChain"
    name = "OpenAIToolsAgent"

    inputs = [
        *LCToolsAgentComponent._base_inputs,
        HandleInput(
            name="llm",
            display_name="Language Model",
            input_types=["LanguageModel", "ToolEnabledLanguageModel"],
            required=True,
        ),
        MultilineInput(
            name="system_prompt",
            display_name="System Prompt",
            info="System prompt for the agent.",
            value="You are a helpful assistant",
        ),
        MultilineInput(
            name="user_prompt", display_name="Prompt", info="This prompt must contain 'input' key.", value="{input}"
        ),
        DataInput(name="chat_history", display_name="Chat History", is_list=True, advanced=True),
    ]

    def get_chat_history_data(self) -> list[Data] | None:
        return self.chat_history

    def create_agent_runnable(self):
        if "input" not in self.user_prompt:
            msg = "Prompt must contain 'input' key."
            raise ValueError(msg)
        messages = [
            ("system", self.system_prompt),
            ("placeholder", "{chat_history}"),
            HumanMessagePromptTemplate(prompt=PromptTemplate(input_variables=["input"], template=self.user_prompt)),
            ("placeholder", "{agent_scratchpad}"),
        ]
        prompt = ChatPromptTemplate.from_messages(messages)
        return create_openai_tools_agent(self.llm, self.tools, prompt)
