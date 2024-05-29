from typing import Optional

from langchain.chains import LLMChain, LLMMathChain

from langflow.custom import CustomComponent
from langflow.field_typing import BaseLanguageModel, BaseMemory, Text


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
            "input_value": {
                "display_name": "Input Value",
                "info": "The input value to pass to the chain.",
            },
        }

    def build(
        self,
        input_value: Text,
        llm: BaseLanguageModel,
        llm_chain: LLMChain,
        input_key: str = "question",
        output_key: str = "answer",
        memory: Optional[BaseMemory] = None,
    ) -> Text:
        chain = LLMMathChain(
            llm=llm,
            llm_chain=llm_chain,
            input_key=input_key,
            output_key=output_key,
            memory=memory,
        )
        response = chain.invoke({input_key: input_value})
        result = response.get(output_key)
        result_str = Text(result)
        self.status = result_str
        return result_str
