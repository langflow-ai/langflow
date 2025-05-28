from langchain.chains import ConversationChain

from langflow.base.chains.model import LCChainComponent
from langflow.field_typing import Message
from langflow.inputs import HandleInput, MultilineInput


class ConversationChainComponent(LCChainComponent):
    display_name = "ConversationChain"
    description = "Chain to have a conversation and load context from memory."
    name = "ConversationChain"
    legacy: bool = True
    icon = "LangChain"

    inputs = [
        MultilineInput(
            name="input_value",
            display_name="Input",
            info="The input value to pass to the chain.",
            required=True,
        ),
        HandleInput(
            name="llm",
            display_name="Language Model",
            input_types=["LanguageModel"],
            required=True,
        ),
        HandleInput(
            name="memory",
            display_name="Memory",
            input_types=["BaseChatMemory"],
        ),
    ]

    def invoke_chain(self) -> Message:
        if not self.memory:
            chain = ConversationChain(llm=self.llm)
        else:
            chain = ConversationChain(llm=self.llm, memory=self.memory)

        result = chain.invoke(
            {"input": self.input_value},
            config={"callbacks": self.get_langchain_callbacks()},
        )
        if isinstance(result, dict):
            result = result.get(chain.output_key, "")

        elif not isinstance(result, str):
            result = result.get("response")
        result = str(result)
        self.status = result
        return Message(text=result)
