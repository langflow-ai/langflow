from langflow.base.prompts.api_utils import process_prompt_template
from langflow.custom import Component
from langflow.io import Output, PromptInput
from langflow.schema.message import Message
from langflow.template.utils import update_template_values


class PromptComponent(Component):
    display_name: str = "Prompt"
    description: str = "Create a prompt template with dynamic variables."
    icon = "prompts"
    trace_type = "prompt"
    name = "Prompt"

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

    def post_code_processing(self, new_build_config: dict, current_build_config: dict):
        """
        This function is called after the code validation is done.
        """
        frontend_node = super().post_code_processing(new_build_config, current_build_config)
        template = frontend_node["template"]["template"]["value"]
        _ = process_prompt_template(
            template=template,
            name="template",
            custom_fields=frontend_node["custom_fields"],
            frontend_node_template=frontend_node["template"],
        )
        # Now that template is updated, we need to grab any values that were set in the current_build_config
        # and update the frontend_node with those values
        update_template_values(new_template=frontend_node, previous_template=current_build_config["template"])
        return frontend_node
