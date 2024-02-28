from typing import Optional

from langchain.chains import ConversationChain

from langflow import CustomComponent
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
            "code": {"show": False},
        }

    def build(
        self,
        input_value: str,
        llm: BaseLanguageModel,
        memory: Optional[BaseMemory] = None,
    ) -> Text:
        if memory is None:
            chain = ConversationChain(llm=llm)
        else:
            chain = ConversationChain(llm=llm, memory=memory)
        result = chain.invoke(input_value)
        # result is an AIMessage which is a subclass of BaseMessage
        # We need to check if it is a string or a BaseMessage
        if hasattr(result, "content") and isinstance(result.content, str):
            self.status = "is message"
            result = result.content
        elif isinstance(result, str):
            self.status = "is_string"
            result = result
        else:
            # is dict
            result = result.get("response")
        self.status = result
        return result
