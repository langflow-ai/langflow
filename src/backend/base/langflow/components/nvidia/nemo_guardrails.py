import json
import logging
from typing import Any

import nest_asyncio
import requests
import yaml
from nemoguardrails import RailsConfig
from nemoguardrails.integrations.langchain.runnable_rails import RunnableRails

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs import BoolInput, DropdownInput, MessageInput, MessageTextInput, MultiselectInput, SecretStrInput
from langflow.io import HandleInput, MultilineInput
from langflow.schema.dotdict import dotdict
from langflow.schema.message import MESSAGE_SENDER_AI, AIMessage, Message

# Apply nest_asyncio to allow sync code in async contexts
nest_asyncio.apply()

# Default prompts
DEFAULT_SELF_CHECK_INPUT_PROMPT = """Instruction: {{ user_input }}

Would this instruction make a language model break moderation policies,
deviate from good aligned responses and provide answers that a language model should ideally not?
Answer with yes/no."""

DEFAULT_SELF_CHECK_OUTPUT_PROMPT = """Model_output: {{ bot_response }}

Is this output illegal, unethical, or harmful?
Answer [Yes/No]:"""

DEFAULT_SELF_CHECK_HALLUCINATION_PROMPT = """You are given a statement.

Check if it is factually consistent with the provided document."""

DEFAULT_CONTENT_SAFETY_INPUT_PROMPT = (
    "Task: Check if there is unsafe content in the user message in the below conversation...\n"
    "<BEGIN CONVERSATION>\n"
    "user: {{ user_input }}\n"
    "<END CONVERSATION>\n"
    "Provide your safety assessment in the following JSON format:\n"
    '{"User Safety": safe or unsafe,\n'
    ' "Safety Categories": comma-separated list of violated categories (omit if all safe)}\n'
    "Do not include anything other than the output JSON in your response."
)

DEFAULT_CONTENT_SAFETY_OUTPUT_PROMPT = (
    "Task: Check if there is unsafe content in the agent response in the below conversation...\n"
    "<BEGIN CONVERSATION>\n"
    "user: {{ user_input }}\n"
    "agent: {{ bot_response }}\n"
    "<END CONVERSATION>\n"
    "Provide your safety assessment in the following JSON format:\n"
    '{"Response Safety": safe or unsafe,\n'
    ' "Safety Categories": comma-separated list of violated categories (omit if all safe)}\n'
    "Do not include anything other than the output JSON in your response."
)

DEFAULT_TOPIC_CONTROL_INPUT_PROMPT = "Ensure that the input stays within the allowed discussion topics."

DEFAULT_OFF_TOPIC_MESSAGE = (
    "I apologize, but I can only discuss topics related to [your specific domain/topic]. "
    "Is there something else I can help you with?"
)


class GuardrailsLanguageModel:
    """Wrapper class that makes RunnableRails properly implement the LanguageModel interface."""

    def __init__(self, runnable_rails: RunnableRails):
        self._runnable_rails = runnable_rails

    def invoke(self, inputs, **kwargs):
        """Delegate to the underlying RunnableRails."""
        return self._runnable_rails.invoke(inputs, **kwargs)

    def stream(self, inputs, **kwargs):
        """Delegate to the underlying RunnableRails."""
        return self._runnable_rails.stream(inputs, **kwargs)

    def with_config(self, config, **kwargs):
        """Delegate to the underlying RunnableRails."""
        return GuardrailsLanguageModel(self._runnable_rails.with_config(config, **kwargs))

    def bind_tools(self, tools, **kwargs):
        """Delegate to the underlying RunnableRails."""
        return GuardrailsLanguageModel(self._runnable_rails.bind_tools(tools, **kwargs))

    def __getattr__(self, name):
        """Delegate any other attributes to the underlying RunnableRails."""
        return getattr(self._runnable_rails, name)


class NVIDIANeMoGuardrailsComponent(LCModelComponent):
    display_name = "NeMo Guardrails"
    description = (
        "Apply guardrails to LLM interactions. Set guardrail definitions via the provided options, "
        "or provide directly as multiline text"
    )
    icon = "NVIDIA"
    name = "NVIDIANemoGuardrails"
    beta = True

    file_types = ["yaml"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set default rails value if not already set
        if not hasattr(self, "rails"):
            self.rails = ["content safety input"]

    inputs = [
        MessageInput(name="input_value", display_name="Input"),
        # override system message input from base class to default to hidden
        MultilineInput(
            name="system_message",
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=True,
        ),
        BoolInput(name="stream", display_name="Stream", info="Stream the response from the model.", advanced=True),
        MultiselectInput(
            name="rails",
            display_name="Rails",
            options=[
                "content safety input",
                "content safety output",
                "topic control",
                "jailbreak detection heuristics",
                "jailbreak detection model",
                "self check input",
                "self check output",
                "self check hallucination",
            ],
            value=["content safety input"],
            info=(
                "Guardrails to be applied to the wrapped model's input and/or output. "
                "See the documentation for more details on each guardrail. "
                "If no guardrails are selected, this component serves as a pass through. "
                "Each category of guardrail such as content safety or topic control requires configuration of a model."
            ),
            advanced=False,
            real_time_refresh=True,
        ),
        HandleInput(
            name="llm",
            display_name="Wrapped Language Model",
            info="The language model that Guardrails is wrapping.",
            input_types=["LanguageModel"],
            required=True,
        ),
        # Content Safety Rail Configuration
        MessageTextInput(
            name="content_safety_model_url",
            display_name="Content Safety Model Base URL",
            value="https://integrate.api.nvidia.com/v1",
            advanced=False,
            info="The base URL specifically for content safety models.",
            real_time_refresh=True,
            show=False,
        ),
        MultilineInput(
            name="content_safety_input_prompt",
            display_name="Content Safety Check Input Prompt",
            advanced=False,
            value=DEFAULT_CONTENT_SAFETY_INPUT_PROMPT,
        ),
        MultilineInput(
            name="content_safety_output_prompt",
            display_name="Content Safety Check Output Prompt",
            advanced=False,
            value=DEFAULT_CONTENT_SAFETY_OUTPUT_PROMPT,
        ),
        # Topic Control Rail Configuration
        MessageTextInput(
            name="topic_control_model_url",
            display_name="Topic Control Model Base URL",
            value="https://integrate.api.nvidia.com/v1",
            advanced=False,
            info="The base URL specifically for topic control models.",
            real_time_refresh=True,
            show=False,
        ),
        MultilineInput(
            name="topic_control_input_prompt",
            display_name="Topic Control Check Input Prompt",
            advanced=False,
            value=DEFAULT_TOPIC_CONTROL_INPUT_PROMPT,
        ),
        MultilineInput(
            name="off_topic_message",
            display_name="Off-Topic Message",
            advanced=False,
            value=DEFAULT_OFF_TOPIC_MESSAGE,
            info=(
                "Message to display when the input is off-topic. "
                "Use [your specific domain/topic] as a placeholder for your domain."
            ),
        ),
        # Jailbreak Detection Rail Configuration
        MessageTextInput(
            name="jailbreak_detection_model_url",
            display_name="Jailbreak Detection Model Base URL",
            value="https://ai.api.nvidia.com/v1/security/nvidia/nemoguard-jailbreak-detect",
            advanced=False,
            info="The base URL specifically for jailbreak detection models.",
            real_time_refresh=True,
            show=False,
        ),
        # Self-check Rail Configuration
        MessageTextInput(
            name="self_check_model_url",
            display_name="Self-check Model Base URL",
            value="https://integrate.api.nvidia.com/v1",
            info="The base URL of the API for the model that Guardrails uses for self-check rails.",
            real_time_refresh=True,
            show=False,
        ),
        SecretStrInput(
            name="self_check_model_api_key",
            display_name="Self-check Model API Key",
            info="The API Key for the model that Guardrails uses for self-check rails.",
            value="NVIDIA_API_KEY",
            real_time_refresh=True,
            show=False,
        ),
        DropdownInput(
            name="self_check_model_name",
            display_name="Self-check Model Name",
            value="",
            advanced=False,
            options=[],
            refresh_button=True,
            combobox=True,
            show=False,
        ),
        MultilineInput(
            name="self_check_input_prompt",
            display_name="Self Check Input Prompt",
            advanced=False,
            value=DEFAULT_SELF_CHECK_INPUT_PROMPT,
        ),
        MultilineInput(
            name="self_check_output_prompt",
            display_name="Self Check Output Prompt",
            advanced=False,
            value=DEFAULT_SELF_CHECK_OUTPUT_PROMPT,
        ),
        MultilineInput(
            name="self_check_hallucination_prompt",
            display_name="Self Check Hallucination Prompt",
            advanced=False,
            value=DEFAULT_SELF_CHECK_HALLUCINATION_PROMPT,
        ),
        # Shared Configuration
        SecretStrInput(
            name="guardrail_model_api_key",
            display_name="Guardrail Model API Key",
            info="The API Key used for content safety, topic control, and jailbreak detection models.",
            advanced=False,
            value="NVIDIA_API_KEY",
            show=False,
        ),
        # Advanced Configuration
        MultilineInput(
            name="yaml_content",
            display_name="Guardrails configuration content (YAML)",
            info="Guardrails configuration content in YAML format (overrides other settings).",
            advanced=True,
        ),
        BoolInput(
            name="guardrails_verbose",
            display_name="Verbose Guardrails Logging",
            value=False,
            advanced=True,
            info="If enabled, sets verbose=True on the underlying RunnableRails for detailed debugging output.",
        ),
    ]

    def generate_rails_config(self) -> str:
        """Generates YAML configuration as a string based on user selections."""
        if self.yaml_content:
            return self.yaml_content  # Return user-provided YAML directly

        # Base configuration
        config_dict = {
            "models": [],
            "rails": {
                "config": {},
                "input": {"flows": []},
                "output": {"flows": []},
            },
            "prompts": [],
        }

        # Add dummy main model to work around nemoguardrails bug
        config_dict["models"].append(
            {
                "type": "main",
                "engine": "nvidia_ai_endpoints",
                "model": "mistralai/mixtral-8x7b-instruct-v0.1",
            }
        )

        # Self check rails
        if "self check input" in self.rails:
            config_dict["models"].append(
                {
                    "type": "self_check_input",
                    "engine": "nim",
                    "model": self.self_check_model_name,
                    "parameters": {
                        "base_url": self.self_check_model_url,
                        "api_key": self.self_check_model_api_key,
                    },
                }
            )
            config_dict["rails"]["input"]["flows"].append("self check input")
            config_dict["prompts"].append({"task": "self_check_input", "content": self.self_check_input_prompt})

        if "self check output" in self.rails:
            config_dict["models"].append(
                {
                    "type": "self_check_output",
                    "engine": "nim",
                    "model": self.self_check_model_name,
                    "parameters": {
                        "base_url": self.self_check_model_url,
                        "api_key": self.self_check_model_api_key,
                    },
                }
            )
            config_dict["rails"]["output"]["flows"].append("self check output")
            config_dict["prompts"].append({"task": "self_check_output", "content": self.self_check_output_prompt})

        if "self check hallucination" in self.rails:
            config_dict["models"].append(
                {
                    "type": "self_check_hallucination",
                    "engine": "nim",
                    "model": self.self_check_model_name,
                    "parameters": {
                        "base_url": self.self_check_model_url,
                        "api_key": self.self_check_model_api_key,
                    },
                }
            )
            config_dict["rails"]["output"]["flows"].append("self check hallucination")
            config_dict["prompts"].append(
                {"task": "self_check_hallucination", "content": self.self_check_hallucination_prompt}
            )

        # Content safety rails
        if "content safety input" in self.rails or "content safety output" in self.rails:
            config_dict["models"].append(
                {
                    "type": "content_safety",
                    "engine": "nim",
                    "model": "nvidia/llama-3.1-nemoguard-8b-content-safety",
                    "parameters": {
                        "base_url": self.content_safety_model_url,
                        "api_key": self.guardrail_model_api_key,
                        "max_tokens": 256,
                    },
                }
            )

        if "content safety input" in self.rails:
            config_dict["rails"]["input"]["flows"].append("content safety check input $model=content_safety")
            config_dict["prompts"].append(
                {
                    "task": "content_safety_check_input $model=content_safety",
                    "content": self.content_safety_input_prompt,
                    "output_parser": "nemoguard_parse_prompt_safety",
                    "max_tokens": 50,
                }
            )

        if "content safety output" in self.rails:
            config_dict["rails"]["output"]["flows"].append("content safety check output $model=content_safety")
            config_dict["prompts"].append(
                {
                    "task": "content_safety_check_output $model=content_safety",
                    "content": self.content_safety_output_prompt,
                    "output_parser": "nemoguard_parse_response_safety",
                    "max_tokens": 50,
                }
            )

        # Topic control rails
        if "topic control" in self.rails:
            config_dict["models"].append(
                {
                    "type": "topic_control",
                    "engine": "nim",
                    "model": "nvidia/llama-3.1-nemoguard-8b-topic-control",
                    "parameters": {
                        "base_url": self.topic_control_model_url,
                        "api_key": self.guardrail_model_api_key,
                    },
                }
            )
            config_dict["rails"]["input"]["flows"].append("topic safety check input $model=topic_control")
            config_dict["prompts"].append(
                {
                    "task": "topic_safety_check_input $model=topic_control",
                    "content": self.topic_control_input_prompt,
                }
            )

        # Jailbreak detection rails
        if "jailbreak detection heuristics" in self.rails:
            config_dict["rails"]["input"]["flows"].append("jailbreak detection heuristics")

        if "jailbreak detection model" in self.rails:
            config_dict["rails"]["config"]["jailbreak_detection"] = {
                "nim_full_url": self.jailbreak_detection_model_url,
                "nim_auth_token": self.guardrail_model_api_key,
            }
            config_dict["rails"]["input"]["flows"].append("jailbreak detection model")

        return yaml.dump(config_dict, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def validate_rails_config(self):
        # --- Self-check rails validation ---
        self_check_rails = {"self check input", "self check output", "self check hallucination"}
        if any(rail in self.rails for rail in self_check_rails):
            if not self.self_check_model_url:
                msg = "self_check_model_url must be set when self check rails are enabled"
                raise ValueError(msg)
            if not self.self_check_model_name:
                msg = "You must select a self-check model when using self-check rails."
                raise ValueError(msg)

        # --- Topic control validation ---
        if "topic control" in self.rails and not self.topic_control_model_url:
            msg = "topic_control_model_url must be set when topic control rails are enabled"
            raise ValueError(msg)

        # --- Content safety validation ---
        content_safety_rails = {"content safety input", "content safety output"}
        if any(rail in self.rails for rail in content_safety_rails) and not self.content_safety_model_url:
            msg = "content_safety_model_url must be set when content safety rails are enabled"
            raise ValueError(msg)

        # --- Jailbreak detection validation ---
        if "jailbreak detection model" in self.rails and not self.jailbreak_detection_model_url:
            msg = "jailbreak_detection_model_url must be set when jailbreak detection rails are enabled"
            raise ValueError(msg)

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        self.validate_rails_config()

        yaml_content = self.generate_rails_config()

        if self.guardrails_verbose:
            self._safe_log_config(yaml_content)

        try:
            yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            error_message = "Invalid YAML syntax"
            raise ValueError(error_message) from e

        # Create Colang content if topic control is enabled
        colang_content = None
        if "topic control" in self.rails:
            colang_content = f"""
define bot refuse to respond
  "{self.off_topic_message}"
"""

        config = RailsConfig.from_content(yaml_content=yaml_content, colang_content=colang_content)
        runnable_rails = RunnableRails(config=config, llm=self.llm, verbose=self.guardrails_verbose)

        # Return the wrapped version that properly implements LanguageModel
        return GuardrailsLanguageModel(runnable_rails)

    async def text_response(self) -> Message:
        """Custom text_response method for NeMo Guardrails that properly handles input_value and system_message."""
        output = self.build_model()

        # Prepare the input for RunnableRails
        # RunnableRails expects a dictionary with 'input' key containing the user message
        input_text = ""

        # Add system message if provided
        if self.system_message:
            input_text += f"System: {self.system_message}\n\n"

        # Add user input
        if self.input_value:
            if isinstance(self.input_value, Message):
                input_text += self.input_value.text
            else:
                input_text += str(self.input_value)

        if not input_text.strip():
            msg = "The message you want to send to the model is empty."
            raise ValueError(msg)

        # Create the input dictionary that RunnableRails expects
        input_dict = {"input": input_text}

        try:
            # Configure the model with callbacks and metadata
            output = output.with_config(
                {
                    "run_name": self.display_name,
                    "project_name": self.get_project_name(),
                    "callbacks": self.get_langchain_callbacks(),
                }
            )

            lf_message = None  # Initialize lf_message
            message = None  # Initialize message

            if self.stream:
                # Handle streaming
                if self.is_connected_to_chat_output():
                    # Add a Message for streaming
                    if hasattr(self, "graph"):
                        session_id = self.graph.session_id
                    elif hasattr(self, "_session_id"):
                        session_id = self._session_id
                    else:
                        session_id = None

                    # For streaming, we need to handle the response format differently
                    stream_response = output.stream(input_dict)
                    # Extract text from streaming response if it's a dict
                    if isinstance(stream_response, dict) and "output" in stream_response:
                        stream_text = stream_response["output"]
                    else:
                        stream_text = stream_response

                    model_message = Message(
                        text=stream_text,
                        sender=MESSAGE_SENDER_AI,
                        sender_name="AI",
                        properties={"icon": self.icon, "state": "partial"},
                        session_id=session_id,
                    )
                    model_message.properties.source = self._build_source(self._id, self.display_name, self)
                    lf_message = await self.send_message(model_message)
                    result = lf_message.text
                else:
                    # Non-chat streaming
                    message = output.invoke(input_dict)
                    result = message.content if hasattr(message, "content") else message
            else:
                # Non-streaming
                message = output.invoke(input_dict)
                result = message.content if hasattr(message, "content") else message

            # Always extract the actual text content from RunnableRails response
            if isinstance(result, dict) and "output" in result:
                result = result["output"]
            elif hasattr(message, "content"):
                # Handle AIMessage objects
                result = message.content
            elif isinstance(message, str):
                result = message

            # Set status
            if isinstance(message, AIMessage):
                status_message = self.build_status_message(message)
                self.status = status_message
            elif isinstance(result, dict):
                self.status = json.dumps(result, indent=4)
            else:
                self.status = result

        except Exception as e:
            if message := self._get_exception_message(e):
                raise ValueError(message) from e
            raise

        return lf_message or Message(text=result)

    def get_models(self) -> list[str]:
        """Get available models from NVIDIA API that are suitable for self-check tasks."""
        # List of known good models for self-checking tasks
        known_good_models = {
            "openai/gpt-3.5-turbo-instruct",
            "openai/gpt-4-turbo-instruct",
            "anthropic/claude-3-opus-20240229",
            "anthropic/claude-3-sonnet-20240229",
            "mistral/mistral-large-latest",
            "meta/llama-3.1-8b-instruct",
            "google/gemma-2-2b-instruct",
        }

        url = f"{self.self_check_model_url}/models"
        headers = {"Authorization": f"Bearer {self.self_check_model_api_key}", "Accept": "application/json"}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            model_list = response.json()

            # Filter for models that are in our known good list
            suitable_models = []
            for model in model_list.get("data", []):
                model_id = model["id"]
                if model_id in known_good_models:
                    suitable_models.append(model_id)
        except (requests.RequestException, requests.HTTPError):
            logger = logging.getLogger(__name__)
            logger.exception("Error getting model names")
            # Let the UI handle the empty list case
            return []
        else:
            return suitable_models

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        """Update build configuration and show/hide inputs based on rails selection."""
        # Handle model list updates for self-check models
        if field_name in {"self_check_model_url", "self_check_model_api_key", "self_check_model_name"}:
            try:
                # Only try to fetch models if both URL and API key are provided
                if self.self_check_model_url and self.self_check_model_api_key:
                    models = self.get_models()
                    build_config["self_check_model_name"]["options"] = models
                    # Only set a default value if we have models and no current value
                    if models and (
                        not build_config["self_check_model_name"].get("value")
                        or build_config["self_check_model_name"]["value"] not in models
                    ):
                        build_config["self_check_model_name"]["value"] = models[0]
                else:
                    # Clear options and value if URL or API key is missing
                    build_config["self_check_model_name"]["options"] = []
                    build_config["self_check_model_name"]["value"] = ""
            except Exception as e:
                msg = f"Error getting model names: {e}"
                build_config["self_check_model_name"]["value"] = ""
                build_config["self_check_model_name"]["options"] = []
                raise ValueError(msg) from e

        # Handle dynamic visibility based on rails selection
        if field_name == "rails" or field_name is None:
            # Update the rails value in the component if field_name is "rails"
            if field_name == "rails":
                self.rails = field_value

            # Get current rails selection
            if field_name == "rails":
                selected_rails = set(field_value) if field_value else set()
            # During initialization, use the default value from the component
            elif hasattr(self, "rails"):
                selected_rails = set(self.rails) if self.rails else set()
            else:
                # If rails attribute doesn't exist yet, use the default value
                selected_rails = {"content safety input"}
                self.rails = ["content safety input"]

            # Define rail groups for visibility logic
            self_check_rails = {"self check input", "self check output", "self check hallucination"}
            content_safety_rails = {"content safety input", "content safety output"}
            topic_control_rails = {"topic control"}
            jailbreak_detection_rails = {"jailbreak detection model"}

            # Show/hide inputs based on selected rails
            has_self_check = bool(selected_rails & self_check_rails)
            has_content_safety = bool(selected_rails & content_safety_rails)
            has_topic_control = bool(selected_rails & topic_control_rails)
            has_jailbreak_detection = bool(selected_rails & jailbreak_detection_rails)

            # Set visibility for self-check inputs
            build_config["self_check_model_url"]["show"] = has_self_check
            build_config["self_check_model_api_key"]["show"] = has_self_check
            build_config["self_check_model_name"]["show"] = has_self_check

            # Set visibility for content safety inputs
            build_config["content_safety_model_url"]["show"] = has_content_safety
            build_config["guardrail_model_api_key"]["show"] = (
                has_content_safety or has_topic_control or has_jailbreak_detection
            )

            # Set visibility for topic control inputs
            build_config["topic_control_model_url"]["show"] = has_topic_control

            # Set visibility for jailbreak detection inputs
            build_config["jailbreak_detection_model_url"]["show"] = has_jailbreak_detection

            # Set visibility for prompt inputs based on specific rails
            # Self-check prompts
            build_config["self_check_input_prompt"]["show"] = "self check input" in selected_rails
            build_config["self_check_output_prompt"]["show"] = "self check output" in selected_rails
            build_config["self_check_hallucination_prompt"]["show"] = "self check hallucination" in selected_rails

            # Content safety prompts
            build_config["content_safety_input_prompt"]["show"] = "content safety input" in selected_rails
            build_config["content_safety_output_prompt"]["show"] = "content safety output" in selected_rails

            # Topic control prompts
            build_config["topic_control_input_prompt"]["show"] = "topic control" in selected_rails
            build_config["off_topic_message"]["show"] = "topic control" in selected_rails

        return build_config

    def _safe_log_config(self, yaml_content: str):
        """Safely logs a YAML config with sensitive values redacted."""
        sensitive_keys = {"api_key", "token", "secret", "access_key", "password"}

        def mask_sensitive_values(d):
            """Recursively mask sensitive values in a dictionary."""
            if isinstance(d, dict):
                return {
                    k: "[REDACTED]" if any(s in k.lower() for s in sensitive_keys) else mask_sensitive_values(v)
                    for k, v in d.items()
                }
            if isinstance(d, list):
                return [mask_sensitive_values(item) for item in d]
            return d

        try:
            config_dict = yaml.safe_load(yaml_content)  # Parse YAML into dict
            redacted_dict = mask_sensitive_values(config_dict)  # Mask sensitive data
            redacted_yaml = yaml.dump(redacted_dict, default_flow_style=False, sort_keys=False, allow_unicode=True)
        except yaml.YAMLError:
            redacted_yaml = "[ERROR: Failed to parse YAML]"

        self.log(f"Creating Guardrails with config content:\n {redacted_yaml}")
