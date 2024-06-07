from langchain_core.prompts import ChatPromptTemplate

from langflow.base.prompts.utils import dict_values_to_string
from langflow.custom import CustomComponent
from langflow.field_typing import Prompt, TemplateField, Text
from langflow.schema.schema import Record


class PromptComponent(CustomComponent):
    display_name: str = "Prompt"
    description: str = "Create a prompt template with dynamic variables."
    icon = "prompts"

    def build_config(self):
        return {
            "template": TemplateField(display_name="Template"),
            "code": TemplateField(advanced=True),
        }

    async def build(
        self,
        template: Prompt,
        **kwargs,
    ) -> Record:
        prompt_template = ChatPromptTemplate.from_template(Text(template))
        kwargs = await dict_values_to_string(kwargs)
        messages = list(kwargs.values())
        prompt = prompt_template + messages
        self.status = f'Prompt:\n"{template}"'
        return Record(data={"prompt": prompt.to_json()})
