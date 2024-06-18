from langflow.custom import Component
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
        Output(display_name="Prompt Message", name="prompt", method="build_prompt"),
    ]

    async def build_prompt(
        self,
    ) -> Message:
        prompt = await Message.from_template_and_variables(**self._arguments)
        kwargs = self._arguments.copy()
        kwargs["text"] = prompt.format_text()
        prompt_message = Message(**kwargs)
        self.status = prompt.format_text()
        return prompt_message
