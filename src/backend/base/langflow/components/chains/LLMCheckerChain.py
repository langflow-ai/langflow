from langchain.chains import LLMCheckerChain

from langflow.base.chains.model import LCChainComponent
from langflow.field_typing import Message
from langflow.inputs import MultilineInput, HandleInput


class LLMCheckerChainComponent(LCChainComponent):
    display_name = "LLMCheckerChain"
    description = "Chain for question-answering with self-verification."
    documentation = "https://python.langchain.com/docs/modules/chains/additional/llm_checker"
    name = "LLMCheckerChain"

    inputs = [
        MultilineInput(
            name="input_value", display_name="Input", info="The input value to pass to the chain.", required=True
        ),
        HandleInput(name="llm", display_name="Language Model", input_types=["LanguageModel"], required=True),
    ]

    def invoke_chain(self) -> Message:
        chain = LLMCheckerChain.from_llm(llm=self.llm)
        response = chain.invoke({chain.input_key: self.input_value})
        result = response.get(chain.output_key, "")
        result = str(result)
        self.status = result
        return Message(text=result)
