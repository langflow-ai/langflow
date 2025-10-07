from lfx.base.prompts.api_utils import process_prompt_template
from lfx.custom.custom_component.component import Component
from lfx.inputs.input_mixin import FieldTypes
from lfx.inputs.inputs import DefaultPromptField
from lfx.io import Output, PromptInput
from lfx.schema.message import Message
from lfx.template.utils import update_template_values
from lfx.utils.mustache_security import validate_mustache_template


class MustachePromptComponent(Component):
    display_name: str = "Prompt"
    description: str = "Create a prompt template with dynamic variables."
    icon = "prompts"
    trace_type = "prompt"

    inputs = [
        PromptInput(name="template", display_name="Template", field_type=FieldTypes.MUSTACHE_PROMPT),
    ]

    outputs = [
        Output(display_name="Prompt Message", name="prompt", method="build_prompt"),
    ]

    async def build_prompt(
        self,
    ) -> Message:
        prompt = await Message.from_template_and_variables(template_format="mustache", **self._attributes)
        self.status = prompt.text
        return prompt

    def _update_template(self, frontend_node: dict):
        prompt_template = frontend_node["template"]["template"]["value"]
        # Validate mustache template for security
        validate_mustache_template(prompt_template)
        custom_fields = frontend_node["custom_fields"]
        frontend_node_template = frontend_node["template"]
        _ = process_prompt_template(
            template=prompt_template,
            name="template",
            custom_fields=custom_fields,
            frontend_node_template=frontend_node_template,
            is_mustache=True,
        )
        return frontend_node

    async def update_frontend_node(self, new_frontend_node: dict, current_frontend_node: dict):
        """This function is called after the code validation is done."""
        frontend_node = await super().update_frontend_node(new_frontend_node, current_frontend_node)
        template = frontend_node["template"]["template"]["value"]
        # Kept it duplicated for backwards compatibility
        _ = process_prompt_template(
            template=template,
            name="template",
            custom_fields=frontend_node["custom_fields"],
            frontend_node_template=frontend_node["template"],
            is_mustache=True,
        )
        # Now that template is updated, we need to grab any values that were set in the current_frontend_node
        # and update the frontend_node with those values
        update_template_values(new_template=frontend_node, previous_template=current_frontend_node["template"])
        return frontend_node

    def _get_fallback_input(self, **kwargs):
        return DefaultPromptField(**kwargs)
