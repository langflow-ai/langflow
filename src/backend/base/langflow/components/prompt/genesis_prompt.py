from langflow.base.prompts.api_utils import process_prompt_template
from langflow.custom.custom_component.component import Component
from langflow.inputs.inputs import DefaultPromptField
from langflow.io import MessageTextInput, Output, PromptInput
from langflow.schema.message import Message
from langflow.template.utils import update_template_values


class GenesisPromptComponent(Component):
    display_name: str = "Genesis Prompt Template"
    description: str = "Create a prompt template with dynamic variables (Genesis version)."
    documentation: str = "https://docs.langflow.org/components-prompts"
    icon = "braces"
    trace_type = "prompt"
    name = "GenesisPrompt"
    priority = 0

    inputs = [
        PromptInput(
            name="template",
            display_name="Template",
        ),
        MessageTextInput(
            name="tool_placeholder",
            display_name="Tool Placeholder",
            tool_mode=True,
            advanced=True,
            info="A placeholder used in tool mode.",
        ),
    ]

    outputs = [
        Output(display_name="Prompt", name="prompt", method="build_prompt"),
    ]

    # ------------------------------------------------------
    # BUILD PROMPT (Core output)
    # ------------------------------------------------------
    async def build_prompt(self) -> Message:
        """Called when the node executes.
        Must return a Message.
        """
        # self._attributes is auto-populated by Langflow
        prompt = Message.from_template(**self._attributes)

        # For UI preview in Langflow
        self.status = prompt.text

        return prompt

    # ------------------------------------------------------
    # INTERNAL: Update Template
    # ------------------------------------------------------
    def _update_template(self, frontend_node: dict):
        """Langflow calls this when the template changes.
        Must mutate and return `frontend_node`.
        """
        prompt_template = frontend_node["template"]["template"]["value"]
        custom_fields = frontend_node["custom_fields"]
        frontend_node_template = frontend_node["template"]

        process_prompt_template(
            template=prompt_template,
            name="template",
            custom_fields=custom_fields,
            frontend_node_template=frontend_node_template,
        )

        return frontend_node

    # ------------------------------------------------------
    # FRONTEND NODE UPDATE HANDLING
    # ------------------------------------------------------
    async def update_frontend_node(self, new_frontend_node: dict, current_frontend_node: dict):
        """Called after Langflow validates the node.
        Ensures template, UI bindings, and dynamic fields stay in sync.
        """
        frontend_node = await super().update_frontend_node(new_frontend_node, current_frontend_node)

        template = frontend_node["template"]["template"]["value"]

        # Process new template into dynamic fields
        process_prompt_template(
            template=template,
            name="template",
            custom_fields=frontend_node["custom_fields"],
            frontend_node_template=frontend_node["template"],
        )

        # Sync any values previously set by the user
        update_template_values(
            new_template=frontend_node,
            previous_template=current_frontend_node["template"],
        )

        return frontend_node

    # ------------------------------------------------------
    # FALLBACK INPUT PROVIDER
    # ------------------------------------------------------
    def _get_fallback_input(self, **kwargs):
        """Langflow uses this when generating fallback UI fields.
        Must return DefaultPromptField.
        """
        return DefaultPromptField(**kwargs)
