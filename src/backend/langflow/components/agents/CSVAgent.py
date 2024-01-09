from langflow import CustomComponent
from langflow.field_typing import BaseLanguageModel, AgentExecutor


class CSVAgentComponent(CustomComponent):
    display_name = "CSVAgent"
    description = "Construct a CSV agent from a CSV and tools."
    documentation = "https://python.langchain.com/docs/modules/agents/toolkits/csv"

    def build_config(self):
        return {
            "llm": {"display_name": "LLM", "type": BaseLanguageModel},
            "path": {"display_name": "Path", "type": "file", "suffixes": [".csv"], "file_types": ["csv"]},
        }

    def build(
        self,
        llm: BaseLanguageModel,
        path: str,
    ) -> AgentExecutor:
        # Instantiate and return the CSV agent class with the provided llm and path
        return AgentExecutor(llm=llm, path=path)
