from langflow.custom import CustomComponent
from langflow.field_typing import TemplateField
from langflow.field_typing.prompt import Prompt


class PromptComponent(CustomComponent):
    display_name: str = "Empty Prompt"
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
    ) -> Prompt:
        prompt = await Prompt.from_template_and_variables(template, kwargs)  # type: ignore
        self.status = prompt.format_text()
        return prompt
