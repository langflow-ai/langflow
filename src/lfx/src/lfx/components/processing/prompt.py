from typing import Any

from pyiter import it

from lfx.base.prompts.api_utils import process_prompt_template
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DefaultPromptField
from lfx.io import DropdownInput, MessageTextInput, Output, PromptInput
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.template.utils import update_template_values


class PromptComponent(Component):
    display_name: str = "Prompt Template"
    description: str = "Create a prompt template with dynamic variables."
    documentation: str = "https://docs.langflow.org/components-prompts"
    icon = "braces"
    trace_type = "prompt"
    name = "Prompt Template"
    priority = 0  # Set priority to 0 to make it appear first

    inputs = [
        DropdownInput(
            name="template_format",
            display_name="Template Format",
            options=["f-string", "jinja2"],
            value="f-string",
            info="Select the template format",
            real_time_refresh=True,
        ),
        PromptInput(name="template", display_name="Template"),
        MessageTextInput(
            name="tool_placeholder",
            display_name="Tool Placeholder",
            tool_mode=True,
            advanced=True,
            info="A placeholder input for tool mode.",
        ),
    ]

    outputs = [
        Output(display_name="Prompt", name="prompt", method="build_prompt"),
    ]

    async def build_prompt(self) -> Message:
        prompt = Message.from_template(**self._get_template_attributes())
        self.status = prompt.text
        return prompt

    def _update_template(self, frontend_node: dict[str, Any]):
        prompt_template = frontend_node["template"]["template"]["value"]
        custom_fields = frontend_node["custom_fields"]
        frontend_node_template = frontend_node["template"]
        _ = process_prompt_template(
            template=prompt_template,
            name="template",
            custom_fields=custom_fields,
            frontend_node_template=frontend_node_template,
        )
        return frontend_node

    async def update_frontend_node(self, new_frontend_node: dict[str, Any], current_frontend_node: dict[str, Any]):
        """This function is called after the code validation is done."""
        frontend_node = await super().update_frontend_node(new_frontend_node, current_frontend_node)
        template = frontend_node["template"]["template"]["value"]
        # Kept it duplicated for backwards compatibility
        _ = process_prompt_template(
            template=template,
            name="template",
            custom_fields=frontend_node["custom_fields"],
            frontend_node_template=frontend_node["template"],
        )
        # Now that template is updated, we need to grab any values that were set in the current_frontend_node
        # and update the frontend_node with those values
        update_template_values(
            new_template=frontend_node,
            previous_template=current_frontend_node["template"],
        )
        return frontend_node

    def _get_fallback_input(self, **kwargs: Any):
        return DefaultPromptField(**kwargs)

    def _get_template_attributes(self):
        attributes = self._attributes
        if self.template_format == "jinja2":
            inputs = it(self.inputs).map(lambda x: x.name).to_set()

            attributes = (
                it(self._attributes.items()).map(lambda x: (x[0], x[1] if x[0] in inputs else map_value(x[1])))
            ).to_dict()
        return attributes


def map_value(x: Any) -> Any:
    if isinstance(x, Message):
        return x.text
    if isinstance(x, Data):
        return x.data
    return x
