from langchain_core.prompts import PromptTemplate
from langflow import CustomComponent
from langflow.field_typing import Prompt, TemplateField, Text
from langflow.schema import Record


class PromptComponent(CustomComponent):
    display_name: str = "Prompt"
    description: str = "A component for creating prompts using templates"
    beta = True

    def build_config(self):
        return {
            "template": TemplateField(display_name="Template"),
            "code": TemplateField(advanced=True),
        }

    def build(
        self,
        template: Prompt,
        **kwargs,
    ) -> Text:
        prompt_template = PromptTemplate.from_template(template)

        for key, value in kwargs.copy().items():
            if isinstance(value, Record):
                kwargs[key] = value.text
        try:
            formated_prompt = prompt_template.format(**kwargs)
        except Exception as exc:
            raise ValueError(f"Error formatting prompt: {exc}") from exc
        self.status = f'Prompt: "{formated_prompt}"'
        return formated_prompt
