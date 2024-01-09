
from langflow import CustomComponent
from langchain.agents import AgentExecutor
from typing import Callable
from langflow.field_typing import (
    BaseLanguageModel,
)
from langchain_community.agent_toolkits.base import BaseToolkit

class JsonAgentComponent(CustomComponent):
    display_name = "JsonAgent"
    description = "Construct a json agent from an LLM and tools."

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "toolkit": {"display_name": "Toolkit"},
        }

    def build(
        self,
        llm: BaseLanguageModel,
        toolkit: BaseToolkit,
    ) -> Callable:
        return AgentExecutor(llm=llm, toolkit=toolkit)
