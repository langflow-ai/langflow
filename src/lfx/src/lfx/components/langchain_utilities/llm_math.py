from langchain.chains import LLMMathChain

from lfx.base.chains.model import LCChainComponent
from lfx.inputs.inputs import HandleInput, MultilineInput
from lfx.schema import Message
from lfx.template.field.base import Output


class LLMMathChainComponent(LCChainComponent):
    display_name = "LLMMathChain"
    description = "Chain that interprets a prompt and executes python code to do math."
    documentation = "https://python.langchain.com/docs/modules/chains/additional/llm_math"
    name = "LLMMathChain"
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

    outputs = [Output(display_name="Message", name="text", method="invoke_chain")]

    def invoke_chain(self) -> Message:
        chain = LLMMathChain.from_llm(llm=self.llm)
        response = chain.invoke(
            {chain.input_key: self.input_value},
            config={"callbacks": self.get_langchain_callbacks()},
        )
        result = response.get(chain.output_key, "")
        result = str(result)
        self.status = result
        return Message(text=result)
