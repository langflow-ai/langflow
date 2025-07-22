from langchain.chains import LLMCheckerChain

from lfx.base.chains.model import LCChainComponent
from lfx.field_typing import Message
from lfx.inputs.inputs import HandleInput, MultilineInput


class LLMCheckerChainComponent(LCChainComponent):
    display_name = "LLMCheckerChain"
    description = "Chain for question-answering with self-verification."
    documentation = "https://python.langchain.com/docs/modules/chains/additional/llm_checker"
    name = "LLMCheckerChain"
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
    ]

    def invoke_chain(self) -> Message:
        chain = LLMCheckerChain.from_llm(llm=self.llm)
        response = chain.invoke(
            {chain.input_key: self.input_value},
            config={"callbacks": self.get_langchain_callbacks()},
        )
        result = response.get(chain.output_key, "")
        result = str(result)
        self.status = result
        return Message(text=result)
