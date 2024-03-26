from langchain_experimental.agents.agent_toolkits.csv.base import create_csv_agent

from langflow.custom import CustomComponent
from langflow.field_typing import AgentExecutor, BaseLanguageModel


class CSVAgentComponent(CustomComponent):
    display_name = "CSVAgent"
    description = "Construct a CSV agent from a CSV and tools."
    documentation = "https://python.langchain.com/docs/modules/agents/toolkits/csv"

    def build_config(self):
        return {
            "llm": {"display_name": "LLM", "type": BaseLanguageModel},
            "path": {"display_name": "Path", "field_type": "file", "suffixes": [".csv"], "file_types": [".csv"]},
            "handle_parsing_errors": {"display_name": "Handle Parse Errors", "advanced": True},
            "agent_type": {
                "display_name": "Agent Type",
                "options": ["zero-shot-react-description", "openai-functions", "openai-tools"],
                "advanced": True,
            },
        }

    def build(
        self, llm: BaseLanguageModel, path: str, handle_parsing_errors: bool = True, agent_type: str = "openai-tools"
    ) -> AgentExecutor:
        # Instantiate and return the CSV agent class with the provided llm and path
        return create_csv_agent(
            llm=llm,
            path=path,
            agent_type=agent_type,
            verbose=True,
            agent_executor_kwargs=dict(handle_parsing_errors=handle_parsing_errors),
        )
