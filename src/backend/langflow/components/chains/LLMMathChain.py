from typing import Callable, Optional, Union
from langflow import CustomComponent
from langchain.chains import LLMChain
from typing import Optional
from langflow.field_typing import (
    BaseLanguageModel,
    BaseMemory,
    Chain,
    BasePromptTemplate
)

class LLMMathChainComponent(CustomComponent):
    display_name = "LLMMathChain"
    description = "Chain that interprets a prompt and executes python code to do math."
    documentation = "https://python.langchain.com/docs/modules/chains/additional/llm_math"

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "prompt": {"display_name": "Prompt"},
            "memory": {"display_name": "Memory"},
            "output_key": {"display_name": "Output Key"},
        }

    def build(
        self,
        llm: BaseLanguageModel,
        prompt: BasePromptTemplate,
        output_key: str="text",
        memory: Optional[BaseMemory] = None,
    ) -> Union[Chain, Callable]:
        return LLMChain(llm=llm, prompt=prompt, output_key=output_key, memory=memory)
