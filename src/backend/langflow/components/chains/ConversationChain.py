from langflow import CustomComponent
from langchain.chains import ConversationChain
from typing import Optional, Union, Callable
from langflow.field_typing import BaseLanguageModel, BaseMemory, Chain


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
            "code": {"show": False},
        }

    def build(
        self,
        llm: BaseLanguageModel,
        memory: Optional[BaseMemory] = None,
    ) -> Union[Chain, Callable]:
        if memory is None:
            return ConversationChain(llm=llm)
        return ConversationChain(llm=llm, memory=memory)
