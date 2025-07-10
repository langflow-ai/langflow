import http.client as http_client
import json
import logging
import time
from contextlib import nullcontext

import httpx
import nest_asyncio
import requests
import yaml
from nemoguardrails import RailsConfig
from nemoguardrails.integrations.langchain.runnable_rails import RunnableRails

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs import BoolInput, DropdownInput, MessageTextInput, MultiselectInput, SecretStrInput
from langflow.io import HandleInput, MultilineInput
from langflow.schema.dotdict import dotdict

# Apply nest_asyncio to allow sync code in async contexts
nest_asyncio.apply()


def setup_logging():
    """Set up logging configuration."""
    # Enable debug logging for httpx and httpcore
    logging.getLogger("httpx").setLevel(logging.DEBUG)
    logging.getLogger("httpcore").setLevel(logging.DEBUG)
    logging.getLogger("nemoguardrails").setLevel(logging.DEBUG)
    # Enable debug logging
    logging.basicConfig(level=logging.DEBUG)


def setup_request_logging():
    """Set up request logging for httpx."""

    def log_request(request):
        logging.debug("\n=== Request Details ===")
        logging.debug("URL: %s", request.url)
        logging.debug("Method: %s", request.method)
        logging.debug("Headers:")
        sensitive_headers = {"authorization", "api-key", "x-api-key", "token", "bearer", "secret"}
        for header, value in request.headers.items():
            if not any(sensitive in header.lower() for sensitive in sensitive_headers):
                logging.debug("  %s: %s", header, value)
            else:
                logging.debug("  %s: [REDACTED]", header)
        logging.debug("Body:")
        # Try to parse and redact sensitive info from body if it's JSON
        try:
            body = request.content.decode("utf-8")
            if body:
                try:
                    body_json = json.loads(body)
                    # Redact common sensitive fields
                    sensitive_fields = {"api_key", "token", "secret", "password", "key", "auth"}
                    for field in sensitive_fields:
                        if field in body_json:
                            body_json[field] = "[REDACTED]"
                    logging.debug(json.dumps(body_json, indent=2))
                except json.JSONDecodeError:
                    # If not JSON, just print the body
                    logging.debug(body)
        except UnicodeDecodeError:
            logging.debug("[Unable to decode body]")
        logging.debug("===================\n")

    return httpx.Client(event_hooks={"request": [log_request]})


class HTTPDebugContext:
    """Context manager for HTTP debug logging."""

    def __init__(self):
        self.original_levels = {}
        self.client = None

    def __enter__(self):
        # Store original logging levels
        self.original_levels = {
            "httpx": logging.getLogger("httpx").level,
            "httpcore": logging.getLogger("httpcore").level,
            "root": logging.getLogger().level,
        }

        # Set debug levels
        logging.getLogger("httpx").setLevel(logging.DEBUG)
        logging.getLogger("httpcore").setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)

        # Set up request logging
        self.client = setup_request_logging()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original logging levels
        for logger_name, level in self.original_levels.items():
            logging.getLogger(logger_name).setLevel(level)

        # Clean up client
        if self.client:
            self.client.close()


def enable_http_debug_logging():
    """Enable all HTTP debug logging."""
    # Set up HTTP connection debugging
    http_client.HTTPConnection.debuglevel = 1

    # Set up basic logging
    logging.basicConfig(level=logging.DEBUG)

    # Enable urllib3 request logging
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True

    # Set up detailed request logging
    setup_logging()
    setup_request_logging()


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

    inputs = [
        *LCModelComponent._base_inputs,
        MultiselectInput(
            name="rails",
            display_name="Rails",
            options=[
                "self check input",
                "self check output",
                "self check hallucination",
                "content safety input",
                "content safety output",
                "topic control",
                "jailbreak detection heuristics",
                "jailbreak detection model",
            ],
            value=["self check input", "self check output"],
            info=(
                "Message to display when the input is off-topic. " "Use [your specific domain/topic] as a placeholder."
            ),
            advanced=True,
        ),
        HandleInput(
            name="llm",
            display_name="Wrapped Language Model",
            info="The language model that Guardrails is wrapping.",
            input_types=["LanguageModel"],
            required=True,
        ),
        # Guardrail API Settings
        MessageTextInput(
            name="self_check_model_url",
            display_name="Self-check Model Base URL",
            value="https://integrate.api.nvidia.com/v1",
            info="The base URL of the API for the model that Guardrails uses for self-check rails.",
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="self_check_model_api_key",
            display_name="Self-check Model API Key",
            info="The API Key for the model that Guardrails uses for self-check rails.",
            value="NVIDIA_API_KEY",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="self_check_model_name",
            display_name="Self-check Model Name",
            value="",
            advanced=False,
            options=[],
            refresh_button=True,
            combobox=True,
        ),
        MessageTextInput(
            name="content_safety_model_url",
            display_name="Content Safety Model Base URL",
            value="https://integrate.api.nvidia.com/v1",
            advanced=True,
            info="The base URL specifically for content safety models.",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="topic_control_model_url",
            display_name="Topic Control Model Base URL",
            value="https://integrate.api.nvidia.com/v1",
            advanced=True,
            info="The base URL specifically for topic control models.",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="jailbreak_detection_model_url",
            display_name="Jailbreak Detection Model Base URL",
            value="https://ai.api.nvidia.com/v1/security/nvidia/nemoguard-jailbreak-detect",
            advanced=True,
            info="The base URL specifically for jailbreak detection models.",
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="guardrail_model_api_key",
            display_name="Guardrail Model API Key",
            info="The API Key used for content safety, topic control, and jailbreak detection models.",
            advanced=True,
            value="NVIDIA_API_KEY",
        ),
        # Advanced Inputs for Prompts
        MultilineInput(
            name="self_check_input_prompt",
            display_name="Self Check Input Prompt",
            advanced=True,
            value=DEFAULT_SELF_CHECK_INPUT_PROMPT,
        ),
        MultilineInput(
            name="self_check_output_prompt",
            display_name="Self Check Output Prompt",
            advanced=True,
            value=DEFAULT_SELF_CHECK_OUTPUT_PROMPT,
        ),
        MultilineInput(
            name="self_check_hallucination_prompt",
            display_name="Self Check Hallucination Prompt",
            advanced=True,
            value=DEFAULT_SELF_CHECK_HALLUCINATION_PROMPT,
        ),
        MultilineInput(
            name="content_safety_input_prompt",
            display_name="Content Safety Check Input Prompt",
            advanced=True,
            value=DEFAULT_CONTENT_SAFETY_INPUT_PROMPT,
        ),
        MultilineInput(
            name="content_safety_output_prompt",
            display_name="Content Safety Check Output Prompt",
            advanced=True,
            value=DEFAULT_CONTENT_SAFETY_OUTPUT_PROMPT,
        ),
        MultilineInput(
            name="topic_control_input_prompt",
            display_name="Topic Control Check Input Prompt",
            advanced=True,
            value=DEFAULT_TOPIC_CONTROL_INPUT_PROMPT,
        ),
        MultilineInput(
            name="off_topic_message",
            display_name="Off-Topic Message",
            advanced=True,
            value=DEFAULT_OFF_TOPIC_MESSAGE,
            info=(
                "Message to display when the input is off-topic. "
                "Use [your specific domain/topic] as a placeholder for your domain."
            ),
        ),
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
        BoolInput(
            name="http_logging",
            display_name="HTTP Request Logging",
            value=False,
            advanced=True,
            info="If enabled, logs detailed HTTP request information (headers and body) with sensitive data redacted.",
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

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        # Validate required URLs are set when corresponding rails are enabled
        if "self check input" in self.rails and not self.self_check_model_url:
            msg = "self_check_model_url must be set when self check rails are enabled"
            raise ValueError(msg)
        if "topic control" in self.rails and not self.topic_control_model_url:
            msg = "topic_control_model_url must be set when topic control rails are enabled"
            raise ValueError(msg)
        if "content safety input" in self.rails and not self.content_safety_model_url:
            msg = "content_safety_model_url must be set when content safety rails are enabled"
            raise ValueError(msg)
        if "jailbreak detection model" in self.rails and not self.jailbreak_detection_model_url:
            msg = "jailbreak_detection_model_url must be set when jailbreak detection rails are enabled"
            raise ValueError(msg)

        yaml_content = self.generate_rails_config()

        if self.guardrails_verbose:
            self._safe_log_config(yaml_content)
            start = time.perf_counter()

        # Use context manager for HTTP debug logging if enabled
        context = HTTPDebugContext() if self.http_logging else nullcontext()
        with context:
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
            guardrails = RunnableRails(config=config, llm=self.llm, verbose=self.guardrails_verbose)

            if self.guardrails_verbose:
                end = time.perf_counter()
                self.log(f"Guardrail creation took {end - start:.6f} seconds")

            return guardrails

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
            "google/gemma-2-9b-it",
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
            logging.exception("Error getting model names")
            # Let the UI handle the empty list case
            return []
        else:
            return suitable_models

    def update_build_config(self, build_config: dotdict, field_name: str | None = None):
        """Update build configuration with fresh model list when key fields change."""
        if field_name in {"self_check_model_url", "self_check_model_api_key"}:
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
