from langflow import CustomComponent
from langchain.chains import LLMCheckerChain
from typing import Union, Callable
from langflow.field_typing import (
    BaseLanguageModel,
    Chain,
)


class LLMCheckerChainComponent(CustomComponent):
    display_name = "LLMCheckerChain"
    description = ""
    documentation = "https://python.langchain.com/docs/modules/chains/additional/llm_checker"

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
        }

    def build(
        self,
        llm: BaseLanguageModel,
    ) -> Union[Chain, Callable]:
        return LLMCheckerChain(llm=llm)
