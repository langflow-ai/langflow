from langflow.custom import Component
from langflow.field_typing.prompt import Prompt
from langflow.inputs import PromptInput
from langflow.schema.message import Message
from langflow.template import Output


class PromptComponent(Component):
    display_name: str = "Prompt"
    description: str = "Create a prompt template with dynamic variables."
    icon = "prompts"

    inputs = [
        PromptInput(name="template", display_name="Template"),
    ]

    outputs = [
        Output(display_name="Prompt", name="prompt", method="build_prompt"),
        Output(display_name="Text", name="text", method="format_prompt"),
    ]

    async def format_prompt(self) -> str:
        prompt = await self.build_prompt()
        formatted_text = prompt.format_text()
        self.status = formatted_text
        return formatted_text

    async def build_prompt(
        self,
    ) -> Prompt:
        kwargs = {k: v for k, v in self._arguments.items() if k != "template"}
        prompt = await Message.from_template_and_variables(self.template, kwargs)
        self.status = prompt.format_text()
        return prompt
