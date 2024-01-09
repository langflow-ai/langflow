
from langflow import CustomComponent
from langchain.agents import ZeroShotAgent
from typing import List, Optional
from langflow.field_typing import (
    BaseLanguageModel,
    BaseTool,
)

class ZeroShotAgentComponent(CustomComponent):
    display_name = "ZeroShotAgent"
    description = "Construct an agent from an LLM and tools."

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "tools": {"display_name": "Tools"},
            "prefix": {"display_name": "Prefix", "multiline": True},
            "suffix": {"display_name": "Suffix", "multiline": True},
        }

    def build(
        self,
        llm: BaseLanguageModel,
        tools: List[BaseTool],
        prefix: Optional[str] = "Answer the following questions as best you can. You have access to the following tools:",
        suffix: Optional[str] = "Begin!\n\nQuestion: {input}\nThought:{agent_scratchpad}",
    ) -> ZeroShotAgent:
        return ZeroShotAgent(llm=llm, tools=tools, prefix=prefix, suffix=suffix)
