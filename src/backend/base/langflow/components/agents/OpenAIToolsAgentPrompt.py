from typing import Optional, List

from langchain.agents import create_openai_tools_agent
from langchain_core.prompts import MessagesPlaceholder

from langflow.base.agents.agent import LCToolsAgentComponent
from langflow.inputs.inputs import HandleInput
from langflow.schema import Data


class OpenAIToolsAgentPromptComponent(LCToolsAgentComponent):
    display_name: str = "OpenAI Tools Agent Prompt"
    description: str = "Agent that uses tools via openai-tools."
    icon = "LangChain"
    beta = True
    name = "OpenAIToolsAgentPrompt"

    inputs = LCToolsAgentComponent._base_inputs + [
        HandleInput(
            name="llm",
            display_name="Language Model",
            input_types=["LanguageModel", "ToolEnabledLanguageModel"],
            required=True,
        ),
        HandleInput(
            name="prompt",
            display_name="Prompt",
            input_types=["ChatPromptTemplate"],
            required=True,
        ),
    ]

    def get_chat_history_data(self) -> Optional[List[Data]]:
        return self.chat_history

    def create_agent_runnable(self):
        self.prompt.append(MessagesPlaceholder("agent_scratchpad"))
        self.prompt.input_variables.append("agent_scratchpad")

        return create_openai_tools_agent(self.llm, self.tools, self.prompt)
