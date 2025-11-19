import re
from textwrap import dedent

# from langflow.custom import Component
from langflow.components.prompt.prompt import PromptComponent
from langflow.io import DropdownInput, Output
from langflow.schema.message import Message
from loguru import logger

from langflow.services.deps import get_prompt_service


class GenesisPromptComponent(PromptComponent):
    display_name = "Genesis Prompt Template"
    description = "Select or edit prompt templates."
    icon = "braces"
    trace_type = "genesis_prompt"
    name = "GenesisPromptComponent"

    inputs = [
        DropdownInput(
            name="saved_prompt",
            display_name="Choose from Templates",
            info="Select a Template",
            refresh_button=True,
            real_time_refresh=True,
        ),
        *PromptComponent.inputs,
    ]
    outputs = [
        Output(display_name="Prompt Message", name="prompt", method="build_prompt", type_=Message),
    ]

    def __init__(self, **data):
        super().__init__(**data)
        self.prompt_service = get_prompt_service()
        self._selected_prompt_name = None  # Track the selected prompt name
        self._attributes["template"] = dedent(
            """
            Given the following context, answer the question.
            Context: {context}

            Question: {question}
            Answer:"""
        )

    @staticmethod
    def _extract_template_content(selected_prompt: dict) -> str:
        """Extract template content from the actual API response structure"""
        logger.info(
            f"Processing selected_prompt: {selected_prompt.get('name', 'Unknown')}"
        )

        # Based on the actual structure, template is in:
        # latest_versions[0]['template'][0]['content']['text']

        try:
            # Check if latest_versions exists
            if "latest_versions" in selected_prompt:
                latest_versions = selected_prompt["latest_versions"]
                logger.info(f"Found latest_versions with {len(latest_versions)} items")

                if latest_versions and len(latest_versions) > 0:
                    first_version = latest_versions[0]
                    logger.info(f"First version keys: {list(first_version.keys())}")

                    # Check if template exists in the first version
                    if "template" in first_version:
                        template_list = first_version["template"]
                        logger.info(
                            f"Found template list with {len(template_list)} items"
                        )

                        if template_list and len(template_list) > 0:
                            first_template = template_list[0]
                            logger.info(
                                f"First template item keys: {list(first_template.keys())}"
                            )

                            # Check for content structure
                            if "content" in first_template:
                                content = first_template["content"]
                                logger.info(f"Found content: {content}")

                                if isinstance(content, dict) and "text" in content:
                                    result = content["text"]
                                    if result and result.strip():
                                        logger.info(
                                            f"Successfully extracted template text: {result[:100]}..."
                                        )
                                        return result
                                    else:
                                        logger.warning("Template text is empty")
                                else:
                                    logger.warning(
                                        f"Content structure unexpected: {content}"
                                    )
                            else:
                                logger.warning("No 'content' field in template item")
                        else:
                            logger.warning("Template list is empty")
                    else:
                        logger.warning("No 'template' field in first version")
                else:
                    logger.warning("latest_versions is empty")
            else:
                logger.warning("No 'latest_versions' field found")

                # Fallback: try direct template field (for backward compatibility)
                if "template" in selected_prompt:
                    template = selected_prompt["template"]
                    logger.info(f"Trying fallback direct template: {template}")

                    if isinstance(template, str) and template.strip():
                        return template
                    elif isinstance(template, list) and template:
                        first_item = template[0]
                        if isinstance(first_item, dict) and "content" in first_item:
                            content = first_item["content"]
                            if isinstance(content, dict) and "text" in content:
                                return content["text"]

        except Exception as e:
            logger.error(f"Error extracting template content: {e}")
            logger.exception("Full error details:")

        logger.error("Failed to extract template content from any expected location")
        return ""

    @staticmethod
    def _extract_variables(template: str) -> list[str]:
        """Extract variables from template - supports both {var} and {{ var }} formats"""
        # Your templates use {{ var }} format based on the seed data
        vars_double = re.findall(r"\{\{\s*(\w+)\s*\}\}", template)
        vars_single = re.findall(r"\{(\w+)\}", template)

        # Combine and deduplicate
        variables = list(set(vars_double + vars_single))
        logger.info(f"Extracted variables from template: {variables}")
        logger.info(
            f"Template used for extraction: {template[:200]}..."
        )  # First 200 chars

        return variables

    async def _validate_and_refresh_template(self) -> bool:
        """Validate that the selected template is still available, if not fetch and re-add it"""
        if not self._selected_prompt_name:
            logger.info("No template selected, validation skipped")
            return True

        try:
            criteria = {"max_results": 100}
            prompts = await self.prompt_service.get_prompts(criteria)
            prompt_list = prompts.get("prompts", [])

            # Check if the selected template still exists
            available_names = [
                p.get("name") for p in prompt_list if isinstance(p, dict)
            ]

            if self._selected_prompt_name in available_names:
                logger.info(
                    f"Template '{self._selected_prompt_name}' is still available"
                )
                return True
            else:
                logger.warning(
                    f"Template '{self._selected_prompt_name}' is no longer available, attempting to refresh..."
                )

                # Try to find the template again and refresh it
                selected_prompt = next(
                    (
                        p
                        for p in prompt_list
                        if p.get("name") == self._selected_prompt_name
                    ),
                    None,
                )

                if selected_prompt:
                    logger.info(
                        f"Found template '{self._selected_prompt_name}' in fresh fetch, refreshing content..."
                    )

                    # Re-extract and update the template content
                    template_content = self._extract_template_content(selected_prompt)

                    if template_content:
                        self._attributes["template"] = template_content
                        if hasattr(self, "template"):
                            self.template = template_content
                        logger.info(
                            f"Successfully refreshed template content: {template_content[:100]}..."
                        )
                        return True
                    else:
                        logger.error(
                            f"Failed to extract content from refreshed template '{self._selected_prompt_name}'"
                        )
                        return False
                else:
                    logger.error(
                        f"Template '{self._selected_prompt_name}' not found even after refresh"
                    )
                    logger.info(f"Available templates: {available_names}")
                    return False

        except Exception as e:
            logger.error(f"Error validating/refreshing selected template: {e}")
            logger.exception("Full error details:")
            # If we can't validate, assume it's still valid to avoid breaking the flow
            return True

    async def build_prompt(self) -> Message:
        # Validate and refresh the selected template if needed
        if self._selected_prompt_name:
            is_valid = await self._validate_and_refresh_template()
            if not is_valid:
                error_message = f"Error: Selected template '{self._selected_prompt_name}' is no longer available and could not be refreshed. Please select a different template."
                logger.error(error_message)
                return Message(text=error_message)

        template = self._attributes.get("template", "")
        variables = self._extract_variables(template)

        for var in variables:
            # Try different case variations
            value = (
                self._attributes.get(var)
                or self._attributes.get(var.lower())
                or self._attributes.get(var.title())
                or ""
            )

            # Replace both {{ var }} and {var} formats
            template = re.sub(
                rf"\{{\{{\s*{re.escape(var)}\s*\}}\}}", str(value), template
            )
            template = re.sub(rf"\{{{re.escape(var)}\}}", str(value), template)

        return Message(text=template)

    async def update_build_config(
        self, build_config, field_value, field_name=None
    ) -> dict:
        if field_name == "saved_prompt":
            try:
                criteria = {"max_results": 100}
                prompts = await self.prompt_service.get_prompts(criteria)
                prompt_list = prompts.get("prompts", [])

                logger.info(f"Retrieved {len(prompt_list)} prompts from service")

                # Extract template names for dropdown
                template_names = [
                    p.get("name", "Unnamed Template")
                    for p in prompt_list
                    if isinstance(p, dict)
                ]
                build_config["saved_prompt"]["options"] = template_names
                logger.info(f"Available template names: {template_names}")

                if field_value:
                    logger.info(f"Processing selected prompt: {field_value}")

                    # Store the selected prompt name for validation during build
                    self._selected_prompt_name = field_value

                    # Find the selected prompt
                    selected_prompt = next(
                        (p for p in prompt_list if p.get("name") == field_value), None
                    )

                    if selected_prompt:
                        logger.info(f"Found prompt with name: {field_value}")

                        # Extract template content using the correct SDK format
                        template_content = self._extract_template_content(
                            selected_prompt
                        )

                        if not template_content:
                            logger.error("Failed to extract template content")
                            return build_config

                        logger.info(
                            f"Successfully extracted template: {template_content[:100]}..."
                        )

                        # Update the template in the component
                        self._attributes["template"] = template_content
                        if hasattr(self, "template"):
                            self.template = template_content
                        build_config["template"]["value"] = template_content

                        # Extract variables from the template
                        parameters = self._extract_variables(template_content)

                        if not parameters:
                            logger.info(
                                "No variables found in template - no dynamic fields needed"
                            )
                            return build_config

                        logger.info(f"Found {len(parameters)} parameters: {parameters}")

                        # Remove existing dynamic fields
                        fields_to_remove = [
                            key
                            for key in list(build_config.keys())
                            if isinstance(build_config.get(key, {}), dict)
                            and build_config[key].get("is_custom_field", False)
                        ]

                        for key in fields_to_remove:
                            build_config.pop(key, None)
                            logger.info(f"Removed existing dynamic field: {key}")

                        # Create new dynamic fields for each parameter
                        for param in parameters:
                            param_name = param.strip()
                            if not param_name:
                                continue

                            display_name = param_name.replace("_", " ").title()

                            build_config[param_name] = {
                                "is_custom_field": True,
                                "name": param_name,
                                "display_name": display_name,
                                "value": "",
                                "info": f"Enter value for {display_name}",
                                "required": True,
                                "show": True,
                                "multiline": True,
                                "dynamic": True,
                                "placeholder": f"Enter {display_name.lower()}...",
                                "advanced": False,
                                "field_type": "str",
                                "fileTypes": [],
                                "file_path": "",
                                "input_types": ["Message", "Text"],
                                "list": False,
                                "load_from_db": False,
                                "title_case": False,
                                "type": "str",
                            }

                            logger.info(
                                f"Created dynamic field: {param_name} -> {display_name}"
                            )

                        logger.info(
                            f"Successfully created {len(parameters)} dynamic fields"
                        )

                    else:
                        logger.warning(
                            f"Prompt '{field_value}' not found in available prompts"
                        )
                        logger.info(
                            f"Available prompts: {[p.get('name') for p in prompt_list]}"
                        )

                else:
                    # Clear the selected prompt name if no value is selected
                    self._selected_prompt_name = None

            except Exception as e:
                logger.error(f"Error in update_build_config: {e}")
                logger.exception("Full error details:")
                build_config["saved_prompt"]["options"] = []

        return build_config
