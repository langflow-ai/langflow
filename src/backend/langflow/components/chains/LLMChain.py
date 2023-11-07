from langflow import CustomComponent
from langchain.chains import LLMChain
from typing import Optional, Union, Callable
from langflow.field_typing import (
    BasePromptTemplate,
    BaseLanguageModel,
    BaseMemory,
    Chain,
)


class LLMChainComponent(CustomComponent):
    display_name = "LLMChain"
    description = "Chain to run queries against LLMs"

    def build_config(self):
        return {
            "prompt": {"display_name": "Prompt"},
            "llm": {"display_name": "LLM"},
            "memory": {"display_name": "Memory"},
            "code": {"show": False},
        }

    def build(
        self,
        prompt: BasePromptTemplate,
        llm: BaseLanguageModel,
        memory: Optional[BaseMemory] = None,
    ) -> Union[Chain, Callable]:
        return LLMChain(prompt=prompt, llm=llm, memory=memory)
