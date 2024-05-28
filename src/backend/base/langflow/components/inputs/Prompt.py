from langchain_core.prompts import PromptTemplate

from langflow.custom import CustomComponent
from langflow.field_typing import Prompt, TemplateField, Text


class PromptComponent(CustomComponent):
    display_name: str = "Prompt"
    description: str = "Create a prompt template with dynamic variables."
    icon = "prompts"

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
        from langflow.base.prompts.utils import dict_values_to_string

        prompt_template = PromptTemplate.from_template(Text(template))
        kwargs = dict_values_to_string(kwargs)
        kwargs = {k: "\n".join(v) if isinstance(v, list) else v for k, v in kwargs.items()}
        try:
            formated_prompt = prompt_template.format(**kwargs)
        except Exception as exc:
            raise ValueError(f"Error formatting prompt: {exc}") from exc
        self.status = f'Prompt:\n"{formated_prompt}"'
        return formated_prompt
