import json
from dataclasses import asdict, dataclass, field
from typing import Any

from loguru import logger
from nemo_microservices import AsyncNeMoMicroservices

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import (
    BoolInput,
    DropdownInput,
    MessageInput,
    MultilineInput,
    MultiselectInput,
    SecretStrInput,
    StrInput,
)
from lfx.io import MessageTextInput, Output
from lfx.schema.content_block import ContentBlock
from lfx.schema.content_types import ErrorContent
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message

# GUARDRAIL_MODEL_INTERNAL_URL = "http://ai-platform-proxy.ai-platform.svc.cluster.local:8080/v1"
GUARDRAIL_MODEL_INTERNAL_URL = "http://nvidia-nim-proxy-nemo-nim-proxy.nvidia-nim-proxy.svc.cluster.local:8000/v1"

# Default prompts (shared between components)
DEFAULT_CONTENT_SAFETY_PROMPT = (
    "Task: Check if there is unsafe content in the user or agent messages in the below conversation "
    "in accordance with our safety policy with the below categories. "
    "Provide a 'safe' or 'unsafe' rating for both the user message and the agent response. "
    "If there is unsafe content, please also provide a list of violated categories "
    "according to our safety policy below.\n\n"
    "<BEGIN UNSAFE CONTENT CATEGORIES>\n"
    "S1: Violence.\n"
    "S2: Sexual.\n"
    "S3: Criminal Planning/Confessions.\n"
    "S4: Guns and Illegal Weapons.\n"
    "S5: Controlled/Regulated Substances.\n"
    "S6: Suicide and Self Harm.\n"
    "S7: Sexual (minor).\n"
    "S8: Hate/Identity Hate.\n"
    "S9: PII/Privacy.\n"
    "S10: Harassment.\n"
    "S11: Threat.\n"
    "S12: Profanity.\n"
    "S13: Needs Caution.\n"
    "S14: Other.\n"
    "S15: Manipulation.\n"
    "S16: Fraud/Deception.\n"
    "S17: Malware.\n"
    "S18: High Risk Gov Decision Making.\n"
    "S19: Political/Misinformation/Conspiracy.\n"
    "S20: Copyright/Trademark/Plagiarism.\n"
    "S21: Unauthorized Advice.\n"
    "S22: Illegal Activity.\n"
    "S23: Immoral/Unethical.\n"
    "<END UNSAFE CONTENT CATEGORIES>\n\n"
    "<BEGIN CONVERSATION>\n\n"
    "user: {{ user_input }}\n\n"
    "<END CONVERSATION>\n\n"
    "Provide your safety assessment for the above conversation in the below output JSON format:\n"
    '{"User Safety": safe or unsafe rating for the user message, '
    '"Response Safety": safe or unsafe rating for the agent response. '
    'Omit if no agent response present. "Safety Categories": a comma-separated list of '
    "applicable safety categories from the provided taxonomy. Omit if all safe.}\n\n"
    "Do not include anything other than the output JSON in your response.\n"
    "Output JSON:"
)

DEFAULT_CONTENT_SAFETY_OUTPUT_PROMPT = (
    "Task: Check if there is unsafe content in the user or agent messages in the below conversation "
    "in accordance with our safety policy with the below categories. "
    "Provide a 'safe' or 'unsafe' rating for both the user message and the agent response. "
    "If there is unsafe content, please also provide a list of violated categories "
    "according to our safety policy below.\n\n"
    "<BEGIN UNSAFE CONTENT CATEGORIES>\n"
    "S1: Violence.\n"
    "S2: Sexual.\n"
    "S3: Criminal Planning/Confessions.\n"
    "S4: Guns and Illegal Weapons.\n"
    "S5: Controlled/Regulated Substances.\n"
    "S6: Suicide and Self Harm.\n"
    "S7: Sexual (minor).\n"
    "S8: Hate/Identity Hate.\n"
    "S9: PII/Privacy.\n"
    "S10: Harassment.\n"
    "S11: Threat.\n"
    "S12: Profanity.\n"
    "S13: Needs Caution.\n"
    "S14: Other.\n"
    "S15: Manipulation.\n"
    "S16: Fraud/Deception.\n"
    "S17: Malware.\n"
    "S18: High Risk Gov Decision Making.\n"
    "S19: Political/Misinformation/Conspiracy.\n"
    "S20: Copyright/Trademark/Plagiarism.\n"
    "S21: Unauthorized Advice.\n"
    "S22: Illegal Activity.\n"
    "S23: Immoral/Unethical.\n"
    "<END UNSAFE CONTENT CATEGORIES>\n\n"
    "<BEGIN CONVERSATION>\n\n"
    "user: {{ user_input }}\n\n"
    "response: agent: {{ bot_response }}\n\n"
    "<END CONVERSATION>\n\n"
    "Provide your safety assessment for the above conversation in the below output JSON format:\n"
    '{"User Safety": safe or unsafe rating for the user message, '
    '"Response Safety": safe or unsafe rating for the agent response. '
    'Omit if no agent response present. "Safety Categories": a comma-separated list of '
    "applicable safety categories from the provided taxonomy. Omit if all safe.}\n\n"
    "Do not include anything other than the output JSON in your response.\n"
    "Output JSON:"
)

DEFAULT_TOPIC_CONTROL_PROMPT = (
    "You are to act as a customer service agent, providing users with factual information "
    "in accordance to the knowledge base. Your role is to ensure that you respond only to "
    "relevant queries and adhere to the following guidelines\n\n"
    "Guidelines for the user messages:\n"
    "- Do not answer questions related to personal opinions or advice on user's order, "
    "future recommendations\n"
    "- Do not provide any information on non-company products or services.\n"
    "- Do not answer enquiries unrelated to the company policies.\n"
    "- Do not answer questions asking for personal details about the agent or its creators.\n"
    "- Do not answer questions about sensitive topics related to politics, religion, "
    "or other sensitive subjects.\n"
    "- If a user asks topics irrelevant to the company's customer service relations, "
    "politely redirect the conversation or end the interaction.\n"
    "- Your responses should be professional, accurate, and compliant with customer "
    "relations guidelines, focusing solely on providing transparent, up-to-date "
    "information about the company that is already publicly available.\n"
    "- allow user comments that are related to small talk and chit-chat."
)


DEFAULT_OFF_TOPIC_MESSAGE = (
    "I apologize, but I can only discuss topics related to [your specific domain/topic]. "
    "Is there something else I can help you with?"
)


@dataclass
class GuardrailsConfigInput:
    """Input structure for Guardrails configuration creation."""

    functionality: str = "create"
    fields: dict[str, dict] = field(
        default_factory=lambda: {
            "data": {
                "node": {
                    "name": "create_guardrails_config",
                    "description": "Create a new Guardrails configuration",
                    "display_name": "Create Guardrails Configuration",
                    "field_order": [
                        "01_config_name",
                        "02_config_description",
                        "03_rail_types",
                        "04_content_safety_prompt",
                        "05_content_safety_output_prompt",
                        "06_topic_control_prompt",
                        "07_off_topic_message",
                    ],
                    "template": {
                        "01_config_name": StrInput(
                            name="config_name",
                            display_name="Config Name",
                            info="Name for the guardrails configuration (e.g., my-guardrails-config@v1.0.0)",
                            required=True,
                        ),
                        "02_config_description": MultilineInput(
                            name="config_description",
                            display_name="Config Description",
                            info="Optional description for the guardrails configuration",
                            value="",
                            required=False,
                        ),
                        "03_rail_types": MultiselectInput(
                            name="rail_types",
                            display_name="Rail Types",
                            options=[
                                "content_safety_input",
                                "content_safety_output",
                                "topic_control",
                                "jailbreak_detection",
                            ],
                            value=["content_safety_input"],
                            info="Select the types of guardrails to apply",
                            required=True,
                        ),
                        "04_content_safety_prompt": MultilineInput(
                            name="content_safety_prompt",
                            display_name="Content Safety Input Prompt",
                            info="Prompt for content safety input checking",
                            value=DEFAULT_CONTENT_SAFETY_PROMPT,
                            required=False,
                        ),
                        "05_content_safety_output_prompt": MultilineInput(
                            name="content_safety_output_prompt",
                            display_name="Content Safety Output Prompt",
                            info="Prompt for content safety output checking",
                            value=DEFAULT_CONTENT_SAFETY_OUTPUT_PROMPT,
                            required=False,
                        ),
                        "06_topic_control_prompt": MultilineInput(
                            name="topic_control_prompt",
                            display_name="Topic Control Prompt",
                            info="Prompt for topic control checking",
                            value=DEFAULT_TOPIC_CONTROL_PROMPT,
                            required=False,
                        ),
                        "07_off_topic_message": MultilineInput(
                            name="off_topic_message",
                            display_name="Off-Topic Message",
                            info="Message to display when input is off-topic",
                            value=DEFAULT_OFF_TOPIC_MESSAGE,
                            required=False,
                        ),
                    },
                }
            }
        }
    )


class NVIDIANeMoGuardrailsComponent(Component):
    display_name = "NeMo Guardrails"
    description = (
        "Apply guardrails validation to safeguard LLM interactions using the NeMo Guardrails microservice. "
        "Select a guardrails configuration to validate input or output messages."
    )
    icon = "NVIDIA"
    name = "NVIDIANemoGuardrails"
    beta = True
    trace_type = "guardrails"

    inputs = [
        MessageInput(
            name="input_value",
            display_name="Input",
            info="The message to validate through guardrails",
            required=True,
        ),
        MultilineInput(
            name="system_message",
            display_name="System Message",
            info="Optional system message to prepend to the input",
            advanced=False,
        ),
        # Single authentication setup (like other NeMo components)
        MessageTextInput(
            name="base_url",
            display_name="NeMo Base URL",
            value="https://us-west-2.api-dev.ai.datastax.com/nvidia",
            info="Base URL for NeMo microservices",
            required=True,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="auth_token",
            display_name="Authentication Token",
            info="Authentication token for NeMo microservices",
            required=True,
            real_time_refresh=True,
        ),
        StrInput(
            name="namespace",
            display_name="Namespace",
            value="default",
            info="Namespace for NeMo microservices (e.g., default, my-org)",
            advanced=True,
            required=True,
            real_time_refresh=True,
        ),
        # Guardrails configuration selection
        # dialog_inputs is conditionally set in update_build_config based on allow_config_creation
        DropdownInput(
            name="config",
            display_name="Guardrails Configuration",
            info="Select a guardrails configuration or create a new one",
            options=[],
            refresh_button=True,
            required=True,
            real_time_refresh=True,
            dialog_inputs={},  # Default to empty - will be set by update_build_config if allow_config_creation is True
        ),
        # Validation mode
        DropdownInput(
            name="validation_mode",
            display_name="Validation Mode",
            options=["input", "output"],
            value="input",
            info="Validate input (before LLM) or output (after LLM)",
            required=True,
        ),
        # Advanced option to control configuration creation
        BoolInput(
            name="allow_config_creation",
            display_name="Allow Configuration Creation",
            value=False,
            info="Enable the ability to create new guardrails configurations. "
            "Disable this for cloud deployments where configuration creation is not supported.",
            advanced=True,
            required=False,
            real_time_refresh=True,
        ),
    ]

    # Separate outputs for pass/fail cases (like ConditionalRouterComponent)
    outputs = [
        Output(
            display_name="Passed",
            name="passed_output",
            method="passed_output",
            group_outputs=True,
        ),
        Output(
            display_name="Blocked",
            name="blocked_output",
            method="blocked_output",
            group_outputs=True,
        ),
    ]

    def get_auth_headers(self):
        """Get authentication headers for API requests."""
        if not hasattr(self, "auth_token") or not self.auth_token:
            return {
                "accept": "application/json",
                "Content-Type": "application/json",
            }
        return {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
            "X-Model-Authorization": self.auth_token,
        }

    def get_nemo_client(self) -> AsyncNeMoMicroservices:
        """Get an authenticated NeMo microservices client."""
        return AsyncNeMoMicroservices(
            base_url=self.base_url,
        )

    # Constants for pagination safety checks
    MAX_CONSECUTIVE_SAME_COUNT = 3
    MAX_PAGES_FALLBACK = 10
    MAX_PAGES_SAFETY_LIMIT = 100

    async def fetch_guardrails_configs(self) -> tuple[list[str], list[dict[str, Any]]]:
        """Fetch available guardrails configurations with metadata using pagination.

        Note: The guardrails microservice as of 25.09 release has a pagination bug where it returns
        the same 10 configurations on every page instead of different ones. This method
        works around this bug by detecting duplicate configurations and stopping pagination
        early to prevent infinite loops and duplicate results.
        """
        namespace = getattr(self, "namespace", "default")
        logger.info(f"Fetching guardrails configs from {self.base_url} with namespace: {namespace}")
        try:
            nemo_client = self.get_nemo_client()
            configs = []
            configs_metadata = []
            seen_configs = set()  # Track seen config names to avoid duplicates
            page = 1
            has_more_pages = True
            last_page_item_count = 0
            consecutive_same_count = 0

            while has_more_pages:
                logger.debug(f"Fetching page {page}")
                response = await nemo_client.guardrail.configs.list(page=page, extra_headers=self.get_auth_headers())

                if hasattr(response, "data") and response.data:
                    current_page_item_count = len(response.data)
                    logger.debug(f"Found {current_page_item_count} configs on page {page}")

                    # Check if we're getting the same number of items repeatedly (possible loop)
                    # This is a workaround for the guardrails API bug where it returns the same data on every page
                    if current_page_item_count == last_page_item_count and current_page_item_count > 0:
                        consecutive_same_count += 1
                        logger.debug(
                            f"Same item count as last page ({current_page_item_count}), "
                            f"consecutive count: {consecutive_same_count}"
                        )
                        if consecutive_same_count >= self.MAX_CONSECUTIVE_SAME_COUNT:
                            logger.warning(
                                f"Getting same item count ({current_page_item_count}) repeatedly, "
                                f"stopping pagination to prevent loop"
                            )
                            has_more_pages = False
                            break
                    else:
                        consecutive_same_count = 0

                    last_page_item_count = current_page_item_count
                    new_configs_count = 0

                    for config in response.data:
                        config_name = getattr(config, "name", "")
                        config_description = getattr(config, "description", "")
                        config_created = getattr(config, "created", None)
                        config_updated = getattr(config, "updated", None)

                        logger.debug(f"Processing config: {config_name}")

                        if config_name and config_name not in seen_configs:
                            configs.append(config_name)
                            # Build metadata for this config
                            metadata = self._build_config_metadata(config_description, config_created, config_updated)
                            configs_metadata.append(metadata)
                            seen_configs.add(config_name)
                            new_configs_count += 1
                            logger.debug(f"Added config: {config_name}")
                        elif config_name in seen_configs:
                            # Skip duplicates caused by the API pagination bug
                            logger.debug(f"Skipping duplicate config: {config_name}")

                    # If we didn't get any new unique configs on this page, we might be done
                    if new_configs_count == 0:
                        logger.debug(f"No new unique configs found on page {page}, stopping pagination")
                        has_more_pages = False
                        break
                else:
                    logger.debug(f"No configs found on page {page}")
                    # If we get no data, we've definitely reached the end
                    has_more_pages = False
                    logger.debug("No data found, stopping pagination")
                    break

                # Check if there are more pages using the correct pagination structure
                has_more_pages = False

                # Strategy 1: Check pagination object (primary method based on API structure)
                if hasattr(response, "pagination") and response.pagination:
                    pagination = response.pagination
                    if hasattr(pagination, "total_pages") and hasattr(pagination, "page"):
                        has_more_pages = pagination.page < pagination.total_pages
                        logger.debug(
                            f"Using pagination page comparison: {pagination.page} < "
                            f"{pagination.total_pages} = {has_more_pages}"
                        )
                    elif hasattr(pagination, "has_next") and pagination.has_next is not None:
                        has_more_pages = bool(pagination.has_next)
                        logger.debug(f"Using pagination.has_next field: {has_more_pages}")

                # Strategy 2: Check for has_next field directly on response (fallback)
                elif hasattr(response, "has_next") and response.has_next is not None:
                    has_more_pages = bool(response.has_next)
                    logger.debug(f"Using has_next field: {has_more_pages}")

                # Strategy 3: Check if we got no data (indicates end of data)
                elif len(response.data) == 0:
                    has_more_pages = False
                    logger.debug(f"Using data length comparison: {len(response.data)} == 0 = {has_more_pages}")

                # Strategy 4: Conservative fallback - stop if we've hit a reasonable limit
                else:
                    # Stop after a reasonable number of pages to prevent infinite loops
                    has_more_pages = page < self.MAX_PAGES_FALLBACK
                    logger.debug(f"Using fallback page limit: page < {self.MAX_PAGES_FALLBACK} = {has_more_pages}")

                logger.debug(f"has_more_pages: {has_more_pages}")

                page += 1

                # Safety check to prevent infinite loops
                if page > self.MAX_PAGES_SAFETY_LIMIT:
                    logger.warning("Reached maximum page limit (100), stopping pagination")
                    break

            logger.info(f"Successfully fetched {len(configs)} guardrails configurations across {page - 1} pages")
            return configs, configs_metadata  # noqa: TRY300

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error fetching guardrails configs: {e}")
            logger.error(f"Exception type: {type(e)}")
            if hasattr(e, "response") and e.response:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            return [], []

    def _build_config_metadata(self, description: str, created: Any, updated: Any) -> dict[str, Any]:
        """Build metadata for a guardrails configuration."""
        metadata = {
            "icon": "Settings",
            "description": description if description else "Guardrails configuration",
        }

        if created:
            metadata["created"] = str(created)
        if updated:
            metadata["updated"] = str(updated)

        return metadata

    async def create_guardrails_config(self, config_data: dict) -> str:
        """Create a new guardrails configuration using the NeMo microservices client."""
        config_name = config_data.get("01_config_name")
        namespace = getattr(self, "namespace", "default")
        logger.info(f"Creating guardrails config '{config_name}' in namespace '{namespace}'")
        logger.debug(f"Config data: {config_data}")

        try:
            # Extract config name
            config_name_required = "Config name is required"
            if not config_name:
                raise ValueError(config_name_required)
            logger.debug(f"Config name extracted: {config_name}")

            # Extract description
            description = config_data.get("02_config_description", "")
            logger.debug(f"Description extracted: {description}")

            # Extract rail types
            rail_types = config_data.get("03_rail_types", ["content_safety_input"])
            logger.debug(f"Rail types extracted: {rail_types}")

            # Build the configuration parameters
            logger.debug("Building guardrails parameters...")
            params = self._build_guardrails_params(config_data, rail_types)
            logger.debug(f"Built parameters: {json.dumps(params, indent=2)}")

            # Create the config using the NeMo microservices client
            logger.debug(f"Creating config with name: {config_name}, namespace: {namespace}")
            logger.debug(f"Built parameters: {json.dumps(params, indent=2)}")
            logger.debug(f"Description: {description}")
            logger.debug(f"Using base_url: {self.base_url}")
            logger.debug(f"Auth headers: {self.get_auth_headers()}")

            client = self.get_nemo_client()
            logger.debug("Making API call to guardrail.configs.create...")

            # Call the API with the correct parameter structure
            create_kwargs = {
                "name": config_name,
                "namespace": namespace,
                "data": params,
                "extra_headers": self.get_auth_headers(),
            }

            # Add description if provided
            if description:
                create_kwargs["description"] = description

            logger.debug(
                f"API call kwargs: {json.dumps({k: v for k, v in create_kwargs.items() if k != 'extra_headers'}, indent=2)}"  # noqa: E501
            )

            result = await client.guardrail.configs.create(**create_kwargs)

            logger.debug(f"API call completed. Result type: {type(result)}")
            logger.debug(f"Result object: {result}")

            config_id = result.name
            logger.info(f"Successfully created guardrails config '{config_name}' with ID: {config_id}")
            logger.debug(f"Returning config_id: {config_id}")

            return config_id  # noqa: TRY300

        except Exception as e:
            # Check for HTTP status codes indicating the operation is not supported
            status_code = None
            if hasattr(e, "response") and e.response:
                status_code = getattr(e.response, "status_code", None)
                logger.debug(f"Exception has response with status_code: {status_code}")

            # Handle 501 Not Implemented or 405 Method Not Allowed
            if status_code in (501, 405):
                error_msg = (
                    f"Configuration creation is not supported by this backend deployment. "
                    f"The server returned HTTP {status_code} (Not Implemented). "
                    f"Please disable 'Allow Configuration Creation' in advanced settings."
                )
                logger.error(error_msg)
                logger.error(f"Backend does not support configuration creation: {e!s}")
                raise ValueError(error_msg) from e

            # Handle other errors
            error_msg = f"Failed to create guardrails config '{config_name}': {e!s}"
            logger.error(error_msg)
            logger.error(f"Exception type: {type(e)}")
            logger.error(f"Exception details: {e}")
            if status_code:
                logger.error(f"HTTP status code: {status_code}")
            raise

    def _build_guardrails_params(self, config_data: dict, rail_types: list[str]) -> dict:
        """Build parameters for guardrails configuration."""
        logger.debug(f"Building guardrails params with rail_types: {rail_types}")
        logger.debug(f"Config data keys: {list(config_data.keys())}")

        params = {
            "models": [],  # Required field for guardrails config
            "rails": {
                "input": {"flows": []},
                "output": {"flows": []},
            },
            "prompts": [],
        }

        # Configure content safety rails
        if "content_safety_input" in rail_types or "content_safety_output" in rail_types:
            params["models"].append(
                {
                    "type": "content_safety",
                    "engine": "nim",
                    "model": "nvidia/llama-3.1-nemoguard-8b-content-safety",
                    "parameters": {
                        "base_url": GUARDRAIL_MODEL_INTERNAL_URL,
                    },
                }
            )

        if "content_safety_input" in rail_types:
            params["rails"]["input"]["flows"].append("content safety check input $model=content_safety")
            content_safety_prompt = config_data.get("04_content_safety_prompt", DEFAULT_CONTENT_SAFETY_PROMPT)
            params["prompts"].append(
                {
                    "task": "content_safety_check_input $model=content_safety",
                    "content": content_safety_prompt,
                    "output_parser": "nemoguard_parse_prompt_safety",
                    "max_tokens": 50,
                }
            )

        if "content_safety_output" in rail_types:
            params["rails"]["output"]["flows"].append("content safety check output $model=content_safety")
            content_safety_output_prompt = config_data.get(
                "05_content_safety_output_prompt", DEFAULT_CONTENT_SAFETY_OUTPUT_PROMPT
            )
            params["prompts"].append(
                {
                    "task": "content_safety_check_output $model=content_safety",
                    "content": content_safety_output_prompt,
                    "output_parser": "nemoguard_parse_response_safety",
                    "max_tokens": 50,
                }
            )

        # Configure topic control rail

        if "topic_control" in rail_types:
            params["models"].append(
                {
                    "type": "topic_control",
                    "engine": "nim",
                    "model": "nvidia/llama-3.1-nemoguard-8b-topic-control",
                    "parameters": {
                        "base_url": GUARDRAIL_MODEL_INTERNAL_URL,
                    },
                }
            )
            params["rails"]["input"]["flows"].append("topic safety check input $model=topic_control")
            topic_control_prompt = config_data.get("06_topic_control_prompt", DEFAULT_TOPIC_CONTROL_PROMPT)
            params["prompts"].append(
                {"task": "topic_safety_check_input $model=topic_control", "content": topic_control_prompt}
            )

        # Configure jailbreak detection rail
        if "jailbreak_detection" in rail_types:
            params["rails"]["input"]["flows"].append("jailbreak detection")
            params["rails"]["input"]["flows"].append("jailbreak detection heuristics")

        logger.debug(f"Built guardrails params: {json.dumps(params, indent=2)}")
        return params

    def _get_nemo_exception_message(self, e: Exception):
        """Get a message from an exception."""
        try:
            if hasattr(e, "body") and isinstance(e.body, dict):
                message = e.body.get("message")
                if message:
                    return message
        except Exception:  # noqa: BLE001, S110
            pass
        return None

    async def update_build_config(
        self, build_config: dotdict, field_value: Any, field_name: str | None = None
    ) -> dotdict | str:
        """Update build configuration for the guardrails component."""
        logger.info(f"Updating build config for field: {field_name}, value: {field_value}")

        # Handle allow_config_creation toggle - conditionally enable/disable dialog_inputs
        if field_name == "allow_config_creation":
            allow_creation = bool(field_value) if field_value is not None else False
            logger.info(f"Configuration creation {'enabled' if allow_creation else 'disabled'}")

            # Update the config dropdown's dialog_inputs based on the toggle
            if "config" in build_config:
                if allow_creation:
                    build_config["config"]["dialog_inputs"] = asdict(GuardrailsConfigInput())
                else:
                    # Disable dialog by setting empty dict
                    build_config["config"]["dialog_inputs"] = {}
            return build_config

        # Handle config creation dialog
        if field_name == "config" and isinstance(field_value, dict) and "01_config_name" in field_value:
            # Check if configuration creation is allowed
            allow_creation = getattr(self, "allow_config_creation", False)
            if not allow_creation:
                error_msg = (
                    "Configuration creation is disabled. Enable 'Allow Configuration Creation' "
                    "in advanced settings to create new configurations."
                )
                logger.warning(error_msg)
                return {"error": error_msg}
            try:
                config_id = await self.create_guardrails_config(field_value)
                logger.info(f"Config creation completed with ID: {config_id}")

                # Refresh the config list
                configs, configs_metadata = await self.fetch_guardrails_configs()
                build_config["config"]["options"] = configs
                build_config["config"]["options_metadata"] = configs_metadata

                # Set the newly created config as selected
                config_name = field_value.get("01_config_name")
                if config_name in configs:
                    build_config["config"]["value"] = config_name
                else:
                    pass
                return config_id  # noqa: TRY300
            except Exception as e:  # noqa: BLE001
                logger.error(f"Config creation failed: {e}")
                return {"error": f"Failed to create config: {e}"}

        # Handle config refresh
        if field_name == "config" and (field_value is None or field_value == ""):
            logger.debug("Config refresh requested")
            return await self._handle_config_refresh(build_config)

        # Handle existing config selection
        if field_name == "config" and isinstance(field_value, str):
            logger.debug(f"Config selection: {field_value}")

            # Ensure dialog_inputs is set correctly based on allow_config_creation
            allow_creation = getattr(self, "allow_config_creation", False)
            if "config" in build_config:
                if allow_creation and not build_config["config"].get("dialog_inputs"):
                    build_config["config"]["dialog_inputs"] = asdict(GuardrailsConfigInput())
                elif not allow_creation:
                    build_config["config"]["dialog_inputs"] = {}

            # Populate options if they're empty (similar to KBRetrievalComponent pattern)
            if not build_config.get("config", {}).get("options"):
                try:
                    configs, configs_metadata = await self.fetch_guardrails_configs()
                    build_config["config"]["options"] = configs
                    build_config["config"]["options_metadata"] = configs_metadata
                    logger.debug(f"Populated config options: {configs}")
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error fetching configs for selection: {e}")
                    build_config["config"]["options"] = []
                    build_config["config"]["options_metadata"] = []

            # Set the value in build_config - this is critical as it's used to initialize the component
            build_config["config"]["value"] = field_value

            # Also set it on the component instance to ensure it's available immediately
            # This helps avoid timing issues where the value isn't set before execution
            if hasattr(self, "_inputs") and "config" in self._inputs:
                self._inputs["config"].value = field_value

            # Also set it in _parameters so it's available during component initialization
            if hasattr(self, "_parameters"):
                self._parameters["config"] = field_value

            return build_config

        return build_config

    async def _handle_config_refresh(self, build_config: dotdict) -> dotdict:
        """Handle config refresh with selection preservation."""
        logger.info("Handling config refresh request")

        try:
            # Ensure dialog_inputs is set correctly based on allow_config_creation
            allow_creation = getattr(self, "allow_config_creation", False)
            if "config" in build_config:
                if allow_creation:
                    build_config["config"]["dialog_inputs"] = asdict(GuardrailsConfigInput())
                else:
                    build_config["config"]["dialog_inputs"] = {}

            # Preserve the current selection before refreshing
            current_value = build_config.get("config", {}).get("value")
            logger.debug(f"Preserving current config selection: {current_value}")

            # Fetch available configs
            logger.debug("Refreshing available configs for guardrails")
            configs, configs_metadata = await self.fetch_guardrails_configs()
            build_config["config"]["options"] = configs
            build_config["config"]["options_metadata"] = configs_metadata

            # Restore the current selection if it's still valid
            if current_value and current_value in configs:
                build_config["config"]["value"] = current_value
                logger.debug(f"Restored config selection: {current_value}")
            elif configs and not current_value:
                # Set default config if no current selection
                default_config = None
                for config in configs:
                    if "default" in config.lower():
                        default_config = config
                        break

                if not default_config:
                    default_config = configs[0]

                build_config["config"]["value"] = default_config
                logger.debug(f"Set default config selection: {default_config}")
            elif current_value:
                logger.warning(f"Previously selected config '{current_value}' no longer available in refreshed list")
                # Clear the value when the selected config is no longer available
                build_config["config"]["value"] = ""
            else:
                # No configs available, clear the value
                build_config["config"]["value"] = ""

            logger.info(f"Refreshed {len(configs)} available configs for guardrails")

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error refreshing configs: {e}")
            build_config["config"]["options"] = []
            build_config["config"]["options_metadata"] = []

        return build_config

    def set_attributes(self, params: dict) -> None:
        """Override set_attributes to ensure config value is set on input object."""
        # Call parent implementation first
        super().set_attributes(params)

        # After setting attributes, also set the value on the input object if it exists
        # This ensures the value is available via self.config (which uses __getattr__)
        if "config" in params and hasattr(self, "_inputs") and "config" in self._inputs:
            config_value = params.get("config")
            if config_value:
                self._inputs["config"].value = config_value
            else:
                logger.warning(f"Config key exists in params but value is empty/falsy: '{config_value}'")

    def _pre_run_setup(self):
        """Initialize validation result cache before processing outputs."""
        self._validation_result = None

        # Ensure config value is set if it's available but empty
        # This handles cases where the value might not be properly initialized from build_config
        if hasattr(self, "_inputs") and "config" in self._inputs:
            config_value = self._inputs["config"].value

            # If config is empty, try to get it from _attributes (set via set_attributes) or _parameters
            if not config_value or config_value == "":
                if hasattr(self, "_attributes") and "config" in self._attributes:
                    attr_value = self._attributes.get("config")
                    if attr_value and attr_value != "":
                        self._inputs["config"].value = attr_value
                elif hasattr(self, "_parameters") and "config" in self._parameters:
                    param_value = self._parameters.get("config")
                    if param_value and param_value != "":
                        self._inputs["config"].value = param_value
                # Try vertex template as last resort (the source of truth from build_config)
                elif hasattr(self, "_vertex") and self._vertex:
                    try:
                        template = self._vertex.data.get("node", {}).get("template", {})
                        config_template = template.get("config", {})
                        template_value = config_template.get("value") if isinstance(config_template, dict) else None
                        if template_value and template_value != "":
                            self._inputs["config"].value = template_value
                        else:
                            logger.warning(
                                "Config value is empty and not found in any source - this may cause validation to fail"
                            )
                    except Exception as e:  # noqa: BLE001
                        logger.warning(f"Could not access vertex template: {e}")
                else:
                    logger.warning(
                        "Config value is empty and not found in _attributes or _parameters - "
                        "this may cause validation to fail"
                    )

    async def _validate_input(self) -> tuple[bool, str]:
        """Validate the input through guardrails and return (is_blocked, input_text).

        Results are cached to avoid duplicate API calls when both outputs are evaluated.

        Returns:
            tuple: (is_blocked: bool, input_text: str)
                - is_blocked: True if validation failed, False if passed
                - input_text: The prepared input text that was validated
        """
        # Return cached result if available
        if hasattr(self, "_validation_result") and self._validation_result is not None:
            return self._validation_result

        logger.info("Starting guardrails validation process")

        # Prepare input
        input_text = ""
        if self.system_message:
            input_text += f"{self.system_message}\n\n"
        if self.input_value:
            if isinstance(self.input_value, Message):
                input_text += self.input_value.text
            else:
                input_text += str(self.input_value)

        logger.debug(f"Prepared input text: {input_text[:200]}...")  # Log first 200 chars

        empty_message_error = "The message you want to validate is empty."
        if not input_text.strip():
            logger.error("Empty input text provided")
            raise ValueError(empty_message_error)

        validation_mode = getattr(self, "validation_mode", "input")
        logger.info(f"Processing validation in {validation_mode} mode")

        # Get config value - handle case where it might not be set yet
        # Check both direct attribute access and _inputs dict to diagnose timing issues
        config_value = getattr(self, "config", None)
        if hasattr(self, "_inputs") and "config" in self._inputs:
            input_config_value = self._inputs["config"].value
            # Use the input value if it's set and getattr returned None/empty
            # Handle both None and empty string cases
            if (not config_value or config_value == "") and input_config_value and input_config_value != "":
                config_value = input_config_value

        # Also check _parameters as a fallback (set during component initialization)
        if (not config_value or config_value == "") and hasattr(self, "_parameters") and "config" in self._parameters:
            param_config_value = self._parameters.get("config")
            if param_config_value and param_config_value != "":
                config_value = param_config_value
                # Also set it on the input so it's available for future access
                if hasattr(self, "_inputs") and "config" in self._inputs:
                    self._inputs["config"].value = config_value

        # Try vertex template as last resort (the source of truth from build_config)
        if (not config_value or config_value == "") and hasattr(self, "_vertex") and self._vertex:
            try:
                template = self._vertex.data.get("node", {}).get("template", {})
                config_template = template.get("config", {})
                template_value = config_template.get("value") if isinstance(config_template, dict) else None
                if template_value and template_value != "":
                    config_value = template_value
                    # Also set it on the input so it's available for future access
                    if hasattr(self, "_inputs") and "config" in self._inputs:
                        self._inputs["config"].value = config_value
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Could not access vertex template: {e}")

        # Check for empty string as well as None/empty
        if not config_value or config_value == "":
            error_msg = "Guardrails configuration is required. Please select a configuration from the dropdown."
            logger.error(error_msg)
            logger.error(
                f"Component inputs available: {list(self._inputs.keys()) if hasattr(self, '_inputs') else 'N/A'}"
            )
            if hasattr(self, "_inputs") and "config" in self._inputs:
                logger.error(
                    f"Config input value: '{self._inputs['config'].value}' (type: {type(self._inputs['config'].value)})"
                )
            if hasattr(self, "_parameters"):
                logger.error(f"Config in _parameters: '{self._parameters.get('config', 'NOT_FOUND')}'")
            raise ValueError(error_msg)

        logger.debug(f"Using guardrails config: {config_value}")

        try:
            # Use the proper guardrail.check operation for validation
            client = self.get_nemo_client()

            logger.debug("Making API call to guardrail.check for validation")

            # Determine message role based on validation mode
            role = "user" if validation_mode == "input" else "assistant"

            # Use the dedicated validation endpoint
            # Note: model parameter is required by the API even when using guardrails config_id
            # When guardrails config_id is provided, the model may be ignored or used as a fallback
            # Using a placeholder model name - the actual model is defined in the guardrails config
            validation_response = await client.guardrail.check(
                messages=[{"role": role, "content": input_text}],
                # Required parameter - placeholder when using guardrails config_id
                model="nvidia/llama-3.1-8b-instruct",
                guardrails={"config_id": config_value},
                extra_headers=self.get_auth_headers(),
            )

            logger.debug(f"Validation response: {validation_response}")

            # Check if the response indicates blocking
            # The GuardrailCheckResponse has a 'status' field that can be 'blocked' or 'allowed'
            is_blocked = False

            # First, check the top-level status field (primary method for GuardrailCheckResponse)
            if hasattr(validation_response, "status"):
                status_value = validation_response.status
                # Check for blocked status (case-insensitive comparison for robustness)
                if str(status_value).lower() == "blocked":
                    is_blocked = True

            # Also check rails_status for blocking information (this is important as it may be more specific)
            if not is_blocked and hasattr(validation_response, "rails_status") and validation_response.rails_status:
                # Check if rails_status is a dict-like object before iterating
                rails_status = validation_response.rails_status
                if isinstance(rails_status, dict):
                    # Check if any rail has a blocked status
                    for rail_status in rails_status.values():
                        if hasattr(rail_status, "status"):
                            rail_status_value = rail_status.status
                            if str(rail_status_value).lower() == "blocked":
                                is_blocked = True
                                break

            # Fallback checks if status/rails_status didn't indicate blocking
            if not is_blocked:
                if hasattr(validation_response, "blocked") and validation_response.blocked:
                    # Fallback to blocked boolean field if status not available
                    is_blocked = True
                elif hasattr(validation_response, "choices") and validation_response.choices:
                    # Fallback to checking choices if neither status nor blocked available
                    choice = validation_response.choices[0]
                    if hasattr(choice, "finish_reason") and choice.finish_reason == "guardrail_blocked":
                        is_blocked = True

            if is_blocked:
                logger.info(f"{validation_mode.capitalize()} blocked by guardrails")
                self.status = f"{validation_mode.capitalize()} blocked by guardrails"
            else:
                logger.info(f"{validation_mode.capitalize()} passed guardrails validation")
                self.status = f"{validation_mode.capitalize()} validated successfully"

            # Cache the result
            self._validation_result = (is_blocked, input_text)
            return self._validation_result  # noqa: TRY300

        except Exception as e:
            logger.error(f"Error in validation: {e}")
            logger.error(f"Exception type: {type(e)}")
            if hasattr(e, "response") and e.response:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            if message := self._get_nemo_exception_message(e):
                logger.error(f"Exception message: {message}")
                raise ValueError(message) from e
            raise

    async def passed_output(self) -> Message:
        """Return the validated message when guardrails pass.

        Returns an empty Message if validation failed (so this output won't be used).
        This follows the pattern used by ConditionalRouterComponent.
        """
        is_blocked, input_text = await self._validate_input()
        if is_blocked:
            # Return empty message so this output is not used
            return Message(text="")
        # Validation passed - return the validated input
        return Message(text=input_text, error=False, category="message")

    async def blocked_output(self) -> Message:
        """Return the blocked message when guardrails fail.

        Returns an empty Message if validation passed (so this output won't be used).
        This follows the pattern used by ConditionalRouterComponent.
        """
        is_blocked, _input_text = await self._validate_input()
        if not is_blocked:
            # Return empty message so this output is not used
            return Message(text="")
        # Validation failed - return error message
        validation_mode = getattr(self, "validation_mode", "input")
        error_message = f"I cannot process that {validation_mode}."

        # Create source properties for error display using component's own attributes
        from lfx.schema.properties import Properties
        from lfx.schema.properties import Source as SourceSchema

        component_id = self.get_id() if hasattr(self, "get_id") else getattr(self, "_id", None)
        error_source = SourceSchema(
            id=component_id,
            display_name=self.display_name,
            source=self.name,
        )

        # Create error message with content_blocks for proper display in ErrorView
        # Ensure text is set both as attribute and in data dict for get_text() to work
        error_msg = Message(
            text=error_message,
            error=True,
            category="error",
            properties=Properties(
                text_color="red",
                background_color="red",
                icon="error",
                source=error_source,
            ),
            content_blocks=[
                ContentBlock(
                    title="Guardrails Blocked",
                    contents=[
                        ErrorContent(
                            type="error",
                            component=self.display_name,
                            reason=error_message,
                        )
                    ],
                )
            ],
        )
        # Ensure text is in data dict using set_text() so get_text() works correctly
        # This is critical because ChatOutput calls convert_to_string() which uses get_text()
        # set_text() ensures the text is stored in data[text_key]
        error_msg.set_text(error_message)
        return error_msg
