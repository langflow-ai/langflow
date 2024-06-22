from langflow.custom import Component
from langflow.io import Output, PromptInput
from langflow.schema.message import Message


class PromptComponent(Component):
    display_name: str = "Prompt"
    description: str = "Create a prompt template with dynamic variables."
    icon = "prompts"
    trace_type = "prompt"

    inputs = [
        PromptInput(name="template", display_name="Template"),
    ]

    outputs = [
        Output(display_name="Prompt Message", name="prompt", method="build_prompt"),
    ]

    async def build_prompt(
        self,
    ) -> Message:
        prompt = await Message.from_template_and_variables(**self._attributes)
        self.status = prompt.text
        return prompt
