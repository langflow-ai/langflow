
from langflow import CustomComponent
from langchain.chains import LLMChain
from typing import Optional
from langflow.field_typing import (
    BaseLanguageModel,
    BaseMemory,
)

class LLMMathChainComponent(CustomComponent):
    display_name = "LLMMathChain"
    description = "Chain that interprets a prompt and executes python code to do math."
    documentation = "https://python.langchain.com/docs/modules/chains/additional/llm_math"

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "llm_chain": {"display_name": "LLM Chain"},
            "memory": {"display_name": "Memory"},
            "input_key": {"display_name": "Input Key"},
            "output_key": {"display_name": "Output Key"},
        }

    def build(
        self,
        llm: BaseLanguageModel,
        llm_chain: LLMChain,
        input_key: str,
        output_key: str,
        memory: Optional[BaseMemory] = None,
    ) -> LLMChain:
        return LLMChain(llm=llm, prompt=llm_chain, input_key=input_key, output_key=output_key, memory=memory)
