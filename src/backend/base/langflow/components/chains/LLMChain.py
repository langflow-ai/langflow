from typing import Optional

from langchain.chains.llm import LLMChain

from langflow.field_typing import BaseLanguageModel, BaseMemory, Text
from langflow.interface.custom.custom_component import CustomComponent
from langchain_core.prompts import PromptTemplate


class LLMChainComponent(CustomComponent):
    display_name = "LLMChain"
    description = "Chain to run queries against LLMs"

    def build_config(self):
        return {
            "prompt": {"display_name": "Prompt"},
            "llm": {"display_name": "LLM"},
            "memory": {"display_name": "Memory"},
        }

    def build(
        self,
        template: Text,
        llm: BaseLanguageModel,
        memory: Optional[BaseMemory] = None,
    ) -> Text:
        prompt = PromptTemplate.from_template(template)
        runnable = LLMChain(prompt=prompt, llm=llm, memory=memory)
        result_dict = runnable.invoke({})
        output_key = runnable.output_key
        result = result_dict[output_key]
        self.status = result
        return result
