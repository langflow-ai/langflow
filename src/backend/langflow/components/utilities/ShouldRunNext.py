# Implement ShouldRunNext component
from langchain_core.prompts import PromptTemplate

from langflow import CustomComponent
from langflow.field_typing import BaseLanguageModel, Prompt


class ShouldRunNext(CustomComponent):
    display_name = "Should Run Next"
    description = "Decides whether to run the next component."

    def build_config(self):
        return {
            "prompt": {
                "display_name": "Prompt",
                "info": "The prompt to use for the decision. It should generate a boolean response (True or False).",
            },
            "llm": {
                "display_name": "LLM",
                "info": "The language model to use for the decision.",
            },
        }

    def build(self, template: Prompt, llm: BaseLanguageModel, **kwargs) -> dict:
        # This is a simple component that always returns True
        prompt_template = PromptTemplate.from_template(template)

        attributes_to_check = ["text", "page_content"]
        for key, value in kwargs.items():
            for attribute in attributes_to_check:
                if hasattr(value, attribute):
                    kwargs[key] = getattr(value, attribute)

        chain = prompt_template | llm
        result = chain.invoke(kwargs)
        if hasattr(result, "content") and isinstance(result.content, str):
            result = result.content
        elif isinstance(result, str):
            result = result
        else:
            result = result.get("response")

        if result.lower() not in ["true", "false"]:
            raise ValueError("The prompt should generate a boolean response (True or False).")
        # The string should be the words true or false
        # if not raise an error
        bool_result = result.lower() == "true"
        return {"condition": bool_result, "result": kwargs}
