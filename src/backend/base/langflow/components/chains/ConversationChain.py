from typing import Optional

from langchain.chains import ConversationChain

from langflow.custom import Component
from langflow.field_typing import Message
from langflow.inputs import MultilineInput, HandleInput
from langflow.template import Output


class ConversationChainComponent(Component):
    display_name = "ConversationChain"
    description = "Chain to have a conversation and load context from memory."
    name = "ConversationChain"

    inputs = [
        MultilineInput(
            name="input_value",
            display_name="Input",
            info="The input value to pass to the chain.",
            required=True
        ),
        HandleInput(
            name="llm",
            display_name="Language Model",
            input_types=["LanguageModel"],
            required=True
        ),
        HandleInput(
            name="memory",
            display_name="Memory",
            input_types=["BaseChatMemory"],
        )
    ]

    outputs = [
        Output(display_name="Text", name="text", method="invoke_chain")
    ]

    def invoke_chain(self) -> Message:
        if not self.memory:
            chain = ConversationChain(llm=self.llm)
        else:
            chain = ConversationChain(llm=self.llm, memory=self.memory)

        result = chain.invoke({"input": self.input_value})
        if isinstance(result, dict):
            result = result.get(chain.output_key, "")  # type: ignore

        elif isinstance(result, str):
            result = result
        else:
            result = result.get("response")
        result = str(result)
        self.status = result
        return Message(text=result)
