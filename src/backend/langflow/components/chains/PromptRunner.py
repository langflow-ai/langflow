from langchain.llms.base import BaseLLM
from langchain.prompts import PromptTemplate
from langchain_core.messages import BaseMessage

from langflow import CustomComponent
from langflow.field_typing import Text


class PromptRunner(CustomComponent):
    display_name: str = "Prompt Runner"
    description: str = "Run a Chain with the given PromptTemplate"
    beta: bool = True
    field_config = {
        "llm": {"display_name": "LLM"},
        "prompt": {
            "display_name": "Prompt Template",
            "info": "Make sure the prompt has all variables filled.",
        },
        "code": {"show": False},
    }

    def build(self, llm: BaseLLM, prompt: PromptTemplate, inputs: dict = {}) -> Text:
        chain = prompt | llm
        # The input is an empty dict because the prompt is already filled
        result_message: BaseMessage = chain.invoke(input=inputs)
        if hasattr(result_message, "content"):
            result: str = result_message.content
        elif isinstance(result_message, str):
            result = result_message
        else:
            result = str(result_message)
        self.repr_value = result
        return result
