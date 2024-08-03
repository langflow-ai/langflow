from langchain_experimental.agents.agent_toolkits.csv.base import create_csv_agent

from langflow.base.agents.agent import LCAgentComponent
from langflow.field_typing import AgentExecutor
from langflow.inputs import HandleInput, FileInput, DropdownInput


class CSVAgentComponent(LCAgentComponent):
    display_name = "CSVAgent"
    description = "Construct a CSV agent from a CSV and tools."
    documentation = "https://python.langchain.com/docs/modules/agents/toolkits/csv"
    name = "CSVAgent"

    inputs = LCAgentComponent._base_inputs + [
        HandleInput(name="llm", display_name="Language Model", input_types=["LanguageModel"], required=True),
        FileInput(name="path", display_name="File Path", file_types=["csv"], required=True),
        DropdownInput(
            name="agent_type",
            display_name="Agent Type",
            advanced=True,
            options=["zero-shot-react-description", "openai-functions", "openai-tools"],
            value="openai-tools",
        ),
    ]

    def build_agent(self) -> AgentExecutor:
        return create_csv_agent(llm=self.llm, path=self.path, agent_type=self.agent_type, **self.get_agent_kwargs())
