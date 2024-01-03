from typing import Any, Callable, Optional, Union

from langchain_core.prompts import PromptTemplate as LCPromptTemplate
from langflow.utils.prompt import GenericPromptTemplate
from llama_index.prompts import PromptTemplate as LIPromptTemplate

PromptTemplate = Union[LCPromptTemplate, LIPromptTemplate]


class ChatAdapter:
    def __init__(self, func: Callable, inputs: list[str], output_key: str, prompt: Optional[PromptTemplate] = None):
        self.func = func
        self.input_keys = inputs
        self.output_keys = output_key
        self.prompt = prompt

    @classmethod
    def from_prompt_template(cls, prompt_template: PromptTemplate, func: Callable):
        prompt = GenericPromptTemplate(prompt_template)
        return cls(func, prompt.input_keys, prompt_template)

    def __call__(self, inputs: dict, callbacks: Optional[Any] = None) -> dict:
        return self.func(inputs, callbacks)
