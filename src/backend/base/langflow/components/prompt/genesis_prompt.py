import re

from langflow.custom import Component
from langflow.inputs.inputs import DefaultPromptField
from langflow.io import DropdownInput, MultilineInput, Output
from langflow.schema.message import Message
from loguru import logger

from langflow.services.deps import get_prompt_service


class GenesisPromptComponent(Component):
    display_name: str = "Genesis Prompt Template"
    description: str = "Select prompt templates from published versions."
    documentation: str = "https://docs.langflow.org/components-prompts"
    icon = "braces"
    trace_type = "genesis_prompt"
    name = "Genesis Prompt Template"
    priority = 1

    inputs = [
        DropdownInput(
            name="saved_prompt",
            display_name="Choose from Templates",
            info="Select a Template by prompt_id",
            refresh_button=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="message_type",
            display_name="Message Type",
            info="Select the message type",
            options=["system", "user"],
            value="system",
            real_time_refresh=True,
            advanced=True,  # Hidden initially
        ),
        MultilineInput(
            name="template",
            display_name="Template",
            info="Template content with variables",
            value="",
        ),
    ]

    outputs = [
        Output(
            display_name="Prompt Message",
            name="prompt_message",
            method="build_prompt_message",
        ),
    ]

    def __init__(self, **data):
        super().__init__(**data)
        self._selected_prompt_id = None
        self._selected_version_data = None
        self._current_variables = []

    # -----------------------------------------------------
    # Fetch message content based on selected role
    # -----------------------------------------------------
    def _get_message_by_role(self, role: str) -> str:
        version = self._selected_version_data
        if not version:
            return ""

        chain = version.get("message_chain", []) or []

        for msg in chain:
            if msg.get("role") == role:
                return msg.get("content", "") or ""

        return ""

    # -----------------------------------------------------
    # Replace {{variables}} in template
    # -----------------------------------------------------
    def _replace_variables(self, content: str) -> str:
        if not content:
            return content

        variables = re.findall(r"\{\{(\w+)\}\}", content)

        for var in variables:
            value = getattr(self, var, "")  # Do NOT use .get()
            content = content.replace(f"{{{{{var}}}}}", str(value))

        return content

    # -----------------------------------------------------
    # Build Message Output
    # -----------------------------------------------------
    async def build_prompt_message(self) -> Message:
        template = getattr(self, "template", "") or ""

        if not template:
            self.status = "No template selected"
            return Message(text="")

        try:
            final = self._replace_variables(template)
            self.status = final
            return Message(text=final)
        except Exception as e:
            logger.exception(f"build_prompt_message failed: {e}")
            self.status = "error"
            return Message(text="")

    # -----------------------------------------------------
    # Handle dynamic {{variable}} fields
    # -----------------------------------------------------
    def _process_template_variables(self, template_content: str, build_config: dict):
        vars_found = sorted(list(set(re.findall(r"\{\{(\w+)\}\}", template_content))))

        for var in vars_found:
            field = DefaultPromptField(name=var, display_name=var)

            if var in build_config and isinstance(build_config[var], dict):
                if "value" in build_config[var]:
                    field.value = build_config[var]["value"]

            build_config[var] = field.to_dict()

        # Remove old variables
        for key in list(build_config.keys()):
            if (
                key not in vars_found
                and key not in ["message_type", "saved_prompt", "template"]
                and isinstance(build_config.get(key), dict)
                and build_config[key].get("type") == "prompt-field"
            ):
                build_config.pop(key, None)

        return vars_found

    # -----------------------------------------------------
    # UI Update Handler (Core Sync Logic)
    # -----------------------------------------------------
    async def update_build_config(self, build_config, field_value, field_name=None):
        logger.info(f"update_build_config: {field_name} → {field_value}")

        # -----------------------------
        # Refresh templates (saved_prompt)
        # -----------------------------
        if field_name == "saved_prompt":
            try:
                ps = get_prompt_service()
                if not ps.ready:
                    build_config["saved_prompt"]["options"] = []
                    return build_config

                response = await ps.get_published_prompts()
                versions = response.get("data", {}).get("versions", []) or []

                prompt_ids = sorted(list({v.get("prompt_id") for v in versions}))
                build_config["saved_prompt"]["options"] = prompt_ids

                if field_value:
                    self._selected_prompt_id = field_value
                    selected = next((v for v in versions if v.get("prompt_id") == field_value), None)
                    self._selected_version_data = selected

                    # Reveal message_type
                    build_config["message_type"]["advanced"] = False

                    msg_type = getattr(self, "message_type", "system")
                    content = self._get_message_by_role(msg_type)

                    build_config["template"]["value"] = content

                    if content:
                        self._current_variables = self._process_template_variables(content, build_config)
                else:
                    self._selected_prompt_id = None
                    self._selected_version_data = None
                    
                    # Hide message_type
                    build_config["message_type"]["advanced"] = True
                    build_config["template"]["value"] = ""
                    self._current_variables = []

            except Exception as e:
                logger.exception(f"Error refreshing prompts: {e}")
                build_config["saved_prompt"]["options"] = []

        # -----------------------------
        # Message type switch (system/user)
        # -----------------------------
        elif field_name == "message_type":
            if self._selected_version_data:
                content = self._get_message_by_role(field_value)
                build_config["template"]["value"] = content

                if content:
                    self._current_variables = self._process_template_variables(content, build_config)

        # -----------------------------
        # Sync build_config → component attrs
        # -----------------------------
        for key, val in build_config.items():
            if isinstance(val, dict) and "value" in val:
                setattr(self, key, val["value"])

        return build_config

    # -----------------------------------------------------
    # Fallback for dynamic UI fields
    # -----------------------------------------------------
    def _get_fallback_input(self, **kwargs):
        return DefaultPromptField(**kwargs)