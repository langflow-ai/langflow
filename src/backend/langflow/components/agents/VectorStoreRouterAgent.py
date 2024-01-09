
from langflow import CustomComponent
from langchain.llms import BaseLanguageModel
from langchain.vectorstores import VectorStoreRouterToolkit
from langchain.agents import AgentExecutor
from typing import Callable

class VectorStoreRouterAgentComponent(CustomComponent):
    display_name = "VectorStoreRouterAgent"
    description = "Construct an agent from a Vector Store Router."

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "vectorstoreroutertoolkit": {"display_name": "Vector Store Router Toolkit"},
        }

    def build(
        self, 
        llm: BaseLanguageModel, 
        vectorstoreroutertoolkit: VectorStoreRouterToolkit
    ) -> Callable:
        return AgentExecutor(llm=llm, toolkit=vectorstoreroutertoolkit)
