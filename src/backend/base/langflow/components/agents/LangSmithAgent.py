from langchain import hub
from langchain.agents import create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate, HumanMessagePromptTemplate
from langflow.base.agents.agent import LCToolsAgentComponent
from langflow.inputs import MultilineInput, StrInput, SecretStrInput
from langflow.inputs.inputs import HandleInput


class LangSmithAgentComponent(LCToolsAgentComponent):
    display_name: str = "LangSmith Agent"
    description: str = "Agent that uses LangSmith prompts"
    icon = "LangChain"
    beta = True
    name = "LangSmithAgent"

    inputs = LCToolsAgentComponent._base_inputs + [
        HandleInput(name="llm", display_name="Language Model", input_types=["LanguageModel"], required=True),
        MultilineInput(
            name="system_prompt",
            display_name="System Prompt",
            info="System prompt for the agent.",
            value="You are a helpful assistant.",
        ),
        SecretStrInput(
            name="langchain_api_key",
            display_name="Your LangChain API Key",
            info="The LangChain API Key to use.",
        ),
        StrInput(
            name="langsmith_prompt",
            display_name="LangSmith Prompt",
            info="The LangSmith prompt to use.",
            value="efriis/my-first-prompt",
        ),
    ]

    def create_agent_runnable(self):
        # Pull a public prompt from LangChain Hub
        public_prompt = hub.pull(self.langsmith_prompt)

        messages = [
            ("system", self.system_prompt),
            HumanMessagePromptTemplate(prompt=PromptTemplate(input_variables=["input"], template=public_prompt)),
            ("placeholder", "{agent_scratchpad}"),
        ]

        prompt = ChatPromptTemplate.from_messages(messages)

        return create_tool_calling_agent(self.llm, self.tools, prompt)
