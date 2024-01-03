from typing import Any, Callable, Optional, Union

from langchain_core.prompts import PromptTemplate as LCPromptTemplate
from llama_index.prompts import PromptTemplate as LIPromptTemplate

from langflow.utils.prompt import GenericPromptTemplate

PromptTemplate = Union[LCPromptTemplate, LIPromptTemplate]


class ChatDefinition:
    def __init__(
        self,
        func: Callable,
        inputs: list[str],
        output_key: Optional[str] = None,
        prompt: Optional[PromptTemplate] = None,
    ):
        self.func = func
        self.input_keys = inputs
        self.output_key = output_key
        self.prompt = prompt

    @classmethod
    def from_prompt_template(cls, prompt_template: PromptTemplate, func: Callable):
        prompt = GenericPromptTemplate(prompt_template)
        return cls(func, prompt.input_keys, prompt_template)

    def __call__(self, inputs: dict, callbacks: Optional[Any] = None) -> dict:
        return self.func(inputs, callbacks)
