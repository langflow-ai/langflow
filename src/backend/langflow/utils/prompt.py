from typing import Any, Union

from langchain_core.prompts import PromptTemplate as LCPromptTemplate
from llama_index.prompts import PromptTemplate as LIPromptTemplate

PromptTemplateTypes = Union[LCPromptTemplate, LIPromptTemplate]


class GenericPromptTemplate:
    def __init__(self, prompt_template: PromptTemplateTypes):
        object.__setattr__(self, "prompt_template", prompt_template)

    @property
    def input_keys(self):
        prompt_template = object.__getattribute__(self, "prompt_template")
        if isinstance(prompt_template, LCPromptTemplate):
            return prompt_template.input_variables
        elif isinstance(prompt_template, LIPromptTemplate):
            return prompt_template.template_vars
        else:
            raise TypeError(f"Unknown prompt template type {type(prompt_template)}")

    def to_lc_prompt(self):
        prompt_template = object.__getattribute__(self, "prompt_template")
        if isinstance(prompt_template, LCPromptTemplate):
            return prompt_template
        elif isinstance(prompt_template, LIPromptTemplate):
            return LCPromptTemplate.from_template(prompt_template.get_template())
        else:
            raise TypeError(f"Unknown prompt template type {type(prompt_template)}")

    def to_li_prompt(self):
        prompt_template = object.__getattribute__(self, "prompt_template")
        if isinstance(prompt_template, LIPromptTemplate):
            return prompt_template
        elif isinstance(prompt_template, LCPromptTemplate):
            return LIPromptTemplate(template=prompt_template.template)
        else:
            raise TypeError(f"Unknown prompt template type {type(prompt_template)}")

    def __or__(self, other):
        prompt_template = object.__getattribute__(self, "prompt_template")
        if isinstance(prompt_template, LIPromptTemplate):
            return self.to_lc_prompt() | other
        else:
            raise TypeError(f"Unknown prompt template type {type(other)}")

    def __getattribute__(self, name: str) -> Any:
        if name in {
            "input_keys",
            "to_lc_prompt",
            "to_li_prompt",
            "__or__",
            "prompt_template",
        }:
            return object.__getattribute__(self, name)
        prompt_template = object.__getattribute__(self, "prompt_template")
        return getattr(prompt_template, name)
