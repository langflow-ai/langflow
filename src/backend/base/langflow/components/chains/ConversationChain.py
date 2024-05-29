from typing import Optional

from langchain.chains import ConversationChain

from langflow.custom import CustomComponent
from langflow.field_typing import BaseLanguageModel, BaseMemory, Text


class ConversationChainComponent(CustomComponent):
    display_name = "ConversationChain"
    description = "Chain to have a conversation and load context from memory."

    def build_config(self):
        return {
            "prompt": {"display_name": "Prompt"},
            "llm": {"display_name": "LLM"},
            "memory": {
                "display_name": "Memory",
                "info": "Memory to load context from. If none is provided, a ConversationBufferMemory will be used.",
            },
            "input_value": {
                "display_name": "Input Value",
                "info": "The input value to pass to the chain.",
            },
        }

    def build(
        self,
        input_value: Text,
        llm: BaseLanguageModel,
        memory: Optional[BaseMemory] = None,
    ) -> Text:
        if memory is None:
            chain = ConversationChain(llm=llm)
        else:
            chain = ConversationChain(llm=llm, memory=memory)
        result = chain.invoke({"input": input_value})
        if isinstance(result, dict):
            result = result.get(chain.output_key, "")  # type: ignore

        elif isinstance(result, str):
            result = result
        else:
            result = result.get("response")
        self.status = result
        return str(result)
