import re

from langflow.custom import Component
from langflow.inputs.inputs import DefaultPromptField
from langflow.io import DropdownInput, MessageTextInput, MultilineInput, Output
from langflow.schema.message import Message
from langflow.template.utils import update_template_values
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
            name="message_type",
            display_name="Message Type",
            info="Select the message type to use from template",
            options=["system", "user"],
            value="system",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="saved_prompt",
            display_name="Choose from Templates",
            info="Select a Template by prompt_id",
            refresh_button=True,
            real_time_refresh=True,
        ),
        MultilineInput(
            name="template",
            display_name="Template",
            info="Template content with variables",
            value="",
        ),
    ]
    outputs = [
        Output(display_name="Prompt Message", name="prompt_message", method="build_prompt_message"),
    ]

    def __init__(self, **data):
        super().__init__(**data)
        self._selected_prompt_id = None
        self._selected_version_data = None
        self._current_variables = []

    def _extract_variables_from_role(self, role: str) -> list[str]:
        """Extract variables from message_chain for a specific role using {{var}} format"""
        if not self._selected_version_data:
            return []
        
        variables = set()
        message_chain = self._selected_version_data.get("message_chain", [])
        
        for message in message_chain:
            if message.get("role") == role:
                content = message.get("content", "")
                # Extract {{variable}} format
                found_vars = re.findall(r"\{\{(\w+)\}\}", content)
                variables.update(found_vars)
        
        return sorted(list(variables))

    def _get_message_by_role(self, role: str) -> str:
        """Get message content from message_chain by role"""
        if not self._selected_version_data:
            return ""
        
        message_chain = self._selected_version_data.get("message_chain", [])
        for message in message_chain:
            if message.get("role") == role:
                return message.get("content", "")
        return ""

    def _replace_variables(self, content: str) -> str:
        """Replace {{variables}} in content with actual values"""
        variables = re.findall(r"\{\{(\w+)\}\}", content)
        for var in variables:
            value = self._attributes.get(var, "")
            content = content.replace(f"{{{{{var}}}}}", str(value))
        return content

    async def build_prompt_message(self) -> Message:
        """Build prompt message based on selected message type"""
        message_type = getattr(self, "message_type", "system")
        content = self._get_message_by_role(message_type)
        
        if content:
            content = self._replace_variables(content)
        
        # Set status so the component shows it's been built
        self.status = content if content else "No template selected"
        
        return Message(text=content)

    def _process_template_variables(self, template_content: str, frontend_node_template: dict, custom_fields: dict):
        """Process template variables and create dynamic input fields."""
        # Extract variables from template
        variables = re.findall(r"\{\{(\w+)\}\}", template_content)
        variables = sorted(list(set(variables)))
        
        # Get old custom fields for this component
        old_custom_fields = custom_fields.get("genesis_prompt", []).copy()
        custom_fields["genesis_prompt"] = []
        
        # Add new variables
        for var in variables:
            template_field = DefaultPromptField(name=var, display_name=var)
            if var in frontend_node_template:
                # Preserve existing value
                template_field.value = frontend_node_template[var].get("value", "")
            
            frontend_node_template[var] = template_field.to_dict()
            custom_fields["genesis_prompt"].append(var)
        
        # Remove old variables that are no longer in template
        for old_var in old_custom_fields:
            if old_var not in variables:
                frontend_node_template.pop(old_var, None)
        
        return variables

    async def update_build_config(self, build_config, field_value, field_name=None) -> dict:
        logger.info(f"update_build_config called with field_name: {field_name}, field_value: {field_value}")
        
        # Handle message_type changes
        if field_name == "message_type":
            # When message type changes, re-extract variables for the new type
            if self._selected_version_data:
                message_type = field_value or "system"
                
                # Update template display
                template_content = self._get_message_by_role(message_type)
                build_config["template"]["value"] = template_content
                
                # Process variables and create dynamic fields
                if template_content:
                    custom_fields = {}
                    self._process_template_variables(template_content, build_config, custom_fields)
                    self._current_variables = custom_fields.get("genesis_prompt", [])
                    logger.info(f"Message type changed to {message_type}, variables: {self._current_variables}")
        
        # Handle template selection
        elif field_name == "saved_prompt":
            try:
                # Get the prompt service directly (similar to knowledge hub pattern)
                prompt_service = get_prompt_service()
                if not prompt_service.ready:
                    logger.error("Prompt service is not ready")
                    build_config["saved_prompt"]["options"] = []
                    return build_config

                response = await prompt_service.get_published_prompts()
                
                # Debug the raw response
                logger.info(f"Raw prompt response: {response}")
                
                versions = response.get("data", {}).get("versions", [])
                logger.info(f"Extracted versions: {versions}")

                # Group by prompt_id
                prompt_ids = list(set(v.get("prompt_id") for v in versions if v.get("prompt_id")))
                logger.info(f"Available prompt_ids: {prompt_ids}")
                
                build_config["saved_prompt"]["options"] = prompt_ids

                if field_value:
                    self._selected_prompt_id = field_value
                    logger.info(f"Stored selected prompt_id: {self._selected_prompt_id}")
                    
                    # Find the version for this prompt_id
                    selected_version = next(
                        (v for v in versions if v.get("prompt_id") == field_value), None
                    )

                    if selected_version:
                        self._selected_version_data = selected_version
                        logger.info(f"Selected version for prompt_id: {field_value}")

                        # Get current message type
                        message_type = getattr(self, "message_type", "system")
                        
                        # Update template display
                        template_content = self._get_message_by_role(message_type)
                        build_config["template"]["value"] = template_content
                        
                        # Process variables and create dynamic fields
                        if template_content:
                            custom_fields = {}
                            self._process_template_variables(template_content, build_config, custom_fields)
                            self._current_variables = custom_fields.get("genesis_prompt", [])
                            logger.info(f"Found variables for {message_type}: {self._current_variables}")
                else:
                    self._selected_prompt_id = None
                    self._selected_version_data = None
                    self._current_variables = []
                    build_config["template"]["value"] = ""

            except Exception as e:
                logger.error(f"Error in update_build_config: {e}")
                logger.exception("Full error details:")
                build_config["saved_prompt"]["options"] = []

        return build_config
    
    def _get_fallback_input(self, **kwargs):
        """Provide fallback input for dynamic fields."""
        return DefaultPromptField(**kwargs)
