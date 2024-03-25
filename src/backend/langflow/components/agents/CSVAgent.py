from langchain_experimental.agents.agent_toolkits.csv.base import create_csv_agent

from langflow import CustomComponent
from langflow.field_typing import AgentExecutor, BaseLanguageModel


class CSVAgentComponent(CustomComponent):
    display_name = "CSVAgent"
    description = "Construct a CSV agent from a CSV and tools."
    documentation = "https://python.langchain.com/docs/modules/agents/toolkits/csv"

    def build_config(self):
        return {
            "llm": {"display_name": "LLM", "type": BaseLanguageModel},
            "path": {"display_name": "Path", "field_type": "file", "suffixes": [".csv"], "file_types": [".csv"]},
            "handle_parse_errors": {"display_name": "Handle Parse Errors", "advanced": True},
        }

    def build(self, llm: BaseLanguageModel, path: str, handle_parse_errors: bool = True) -> AgentExecutor:
        # Instantiate and return the CSV agent class with the provided llm and path
        return create_csv_agent(llm=llm, path=path, agent_executor_kwargs=dict(handle_parse_errors=handle_parse_errors))
