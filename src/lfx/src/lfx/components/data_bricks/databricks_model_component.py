import os
from typing import Any

import requests
from langchain_openai import ChatOpenAI
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs.inputs import (
    IntInput,
    SecretStrInput,
    SliderInput,
    StrInput,
)
from langflow.io import DropdownInput
from langflow.schema.message import Message
from openai import OpenAI
from typing_extensions import override

# Common Databricks model names
DATABRICKS_MODELS = [
    "databricks-meta-llama-3-1-8b-instruct",
    "databricks-meta-llama-3-1-70b-instruct",
    "databricks-meta-llama-3-70b-instruct",
    "databricks-llama-2-70b-chat",
    "databricks-mixtral-8x7b-instruct",
    "databricks-dbrx-instruct",
    "databricks-mpt-30b-instruct",
    "databricks-mpt-7b-instruct",
]


class DataBricksModelComponent(LCModelComponent):
    display_name = "DataBricks Model"
    description = "Query models hosted on Databricks using OpenAI-compatible API."
    documentation: str = "https://docs.databricks.com/en/machine-learning/foundation-model-apis/api-reference"
    icon = "DataBricks"
    name = "DataBricksModel"

    inputs = [
        *LCModelComponent._base_inputs,
        StrInput(
            name="base_url",
            display_name="Base URL",
            info="Databricks serving endpoint base URL (e.g., https://dbc-67fdc9e1-5a13.cloud.databricks.com/serving-endpoints)",
            value=os.getenv("DATABRICKS_BASE_URL", ""),
        ),
        SecretStrInput(
            name="api_token",
            display_name="API Token",
            info="Databricks personal access token. Get it from: https://docs.databricks.com/en/dev-tools/auth/pat.html",
            value=os.getenv("DATABRICKS_TOKEN", ""),
            required=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            info="Name of the model deployed on Databricks. Select from dropdown or enter custom model name.",
            options=DATABRICKS_MODELS,
            value=DATABRICKS_MODELS[0],
            combobox=True,
            refresh_button=True,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            info="Maximum number of tokens to generate in the response. Set to 0 for unlimited tokens.",
            value=5000,
            range_spec=RangeSpec(min=0, max=128000),
            advanced=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            info="Sampling temperature between 0 and 2. Higher values make output more random.",
            value=1.0,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            advanced=True,
        )
    ]

    def _safe_str(self, value: Any) -> str:
        """Safely convert a value to string, handling callables and SecretStr objects."""
        if value is None:
            return ""
        if callable(value):
            try:
                result = value()
                return str(result) if result is not None else ""
            except Exception:
                return ""
        if hasattr(value, "get_secret_value"):
            return str(value.get_secret_value())
        return str(value)

    def _extract_text_content(self, value: Any) -> str:
        """Extract text content from various input types, handling JSON strings."""
        import json

        if value is None:
            return ""

        # Handle string input
        if isinstance(value, str):
            # Strip whitespace for checking
            stripped = value.strip()

            # Try to parse as JSON if it looks like JSON (starts with { or [)
            if stripped.startswith(("{", "[")):
                try:
                    parsed = json.loads(stripped)
                    # If it's a dict with a "text" key, extract just the text
                    if isinstance(parsed, dict) and "text" in parsed:
                        text_content = parsed.get("text", "")
                        # Recursively extract if the text itself is JSON
                        if isinstance(text_content, str):
                            extracted = self._extract_text_content(text_content)
                            # Only return extracted if it's different (meaning we found nested JSON)
                            # Otherwise return the text_content as-is
                            if extracted != text_content or not text_content.strip().startswith(("{", "[")):
                                return extracted
                        return str(text_content) if text_content else ""
                    # If it's a list, try to extract text from first item
                    if isinstance(parsed, list) and len(parsed) > 0:
                        return self._extract_text_content(parsed[0])
                except (json.JSONDecodeError, ValueError, TypeError):
                    # Not valid JSON, continue to return as-is
                    pass

            # Also try parsing if it contains JSON-like structure (more lenient check)
            # This handles cases where JSON might be embedded in text
            if "{" in stripped and '"text"' in stripped:
                try:
                    # Try to find JSON object boundaries more flexibly
                    start_idx = stripped.find("{")
                    end_idx = stripped.rfind("}")
                    if start_idx >= 0 and end_idx > start_idx:
                        json_str = stripped[start_idx:end_idx + 1]
                        parsed = json.loads(json_str)
                        if isinstance(parsed, dict) and "text" in parsed:
                            text_content = parsed.get("text", "")
                            if text_content:
                                return str(text_content)
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass

            return value

        # Handle Message objects
        if isinstance(value, Message):
            text = value.text
            if text is None:
                return ""
            # If text is a string, check if it's JSON
            if isinstance(text, str):
                return self._extract_text_content(text)
            # Handle async/iterator cases
            if hasattr(text, "__iter__") and not isinstance(text, str):
                return str(text)
            return str(text)

        # Handle dict that might be a Message-like structure
        if isinstance(value, dict):
            if "text" in value:
                return self._extract_text_content(value["text"])
            # If no text key, convert to string (but this shouldn't happen in normal flow)
            return str(value)

        # Handle list of messages
        if isinstance(value, list):
            # Extract text from each item and join
            texts = []
            for item in value:
                extracted = self._extract_text_content(item)
                if extracted:
                    texts.append(extracted)
            return " ".join(texts) if texts else ""

        # Fallback: convert to string
        return str(value) if value else ""

    def _parse_messages(self, input_value: Any, system_message: str | None = None) -> list[dict[str, str]]:
        """Parse messages input into OpenAI format, extracting only text content."""
        messages = []

        # Add system message if provided
        if system_message:
            messages.append({"role": "system", "content": system_message})

        # Extract text content from input_value
        text_content = self._extract_text_content(input_value)

        if text_content:
            messages.append({"role": "user", "content": text_content})
        elif not system_message:
            # Only add default if no system message either
            messages.append({"role": "user", "content": "Hello"})

        return messages

    def get_models(self) -> list[str]:
        """Fetch available models from Databricks serving endpoint.
        
        Returns:
            list[str]: List of available model names. Falls back to default list if fetch fails.
        """
        api_token = self.api_token
        base_url = self.base_url

        if not api_token or not base_url:
            return DATABRICKS_MODELS

        try:
            # Handle SecretStr
            api_token = self._safe_str(api_token)
            base_url = self._safe_str(base_url)

            # Try to fetch models from OpenAI-compatible /models endpoint
            base_url = base_url.rstrip("/")
            models_url = f"{base_url}/models"

            headers = {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            }

            response = requests.get(models_url, headers=headers, timeout=10)
            response.raise_for_status()
            model_list = response.json()

            # Extract model IDs from the response
            # OpenAI-compatible format: {"data": [{"id": "model-name", ...}, ...]}
            if isinstance(model_list, dict) and "data" in model_list:
                models = [model["id"] for model in model_list["data"] if "id" in model]
                if models:
                    return models
            # Alternative format: list of model names
            elif isinstance(model_list, list):
                return [str(model) for model in model_list if model]

        except requests.RequestException as e:
            self.status = f"Could not fetch models from endpoint, using default list: {e!s}"
        except Exception as e:
            self.status = f"Error fetching models: {e!s}"

        return DATABRICKS_MODELS

    @override
    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Update build config when base_url, api_token, or model_name changes."""
        if field_name in {"base_url", "api_token", "model_name"}:
            models = self.get_models()
            if "model_name" in build_config:
                build_config["model_name"]["options"] = models
        return build_config

    @override
    async def text_response(self) -> Message:
        """Get text response from the model using direct OpenAI client."""
        if not self.input_value and not self.system_message:
            raise ValueError("The message you want to send to the model is empty.")

        # Safely convert inputs to strings
        base_url = self._safe_str(self.base_url)
        api_token = self._safe_str(self.api_token)
        model_name = self._safe_str(self.model_name)

        if not base_url:
            raise ValueError("Base URL is required")

        if not api_token:
            raise ValueError("API Token is required")

        if not model_name:
            raise ValueError("Model name is required")

        try:
            # Initialize OpenAI client with Databricks endpoint
            client = OpenAI(
                api_key=api_token,
                base_url=base_url,
                timeout=60.0
            )

            # Parse messages
            parsed_messages = self._parse_messages(self.input_value, self.system_message)

            # Prepare chat completion parameters
            completion_params = {
                "model": model_name,
                "messages": parsed_messages,
                "max_tokens": self.max_tokens if self.max_tokens and self.max_tokens > 0 else None,
            }

            # Add optional parameters
            if self.temperature is not None:
                completion_params["temperature"] = self.temperature

            # Make the API call
            response = client.chat.completions.create(**completion_params)

            # Extract response content
            raw_response_content = response.choices[0].message.content if response.choices else ""

            # Parse response to extract text content (in case model returns JSON)
            response_content = self._extract_text_content(raw_response_content)

            # Create Message object with cleaned text
            message = Message(text=response_content)

            # Set status with token usage info if available
            if response.usage:
                self.status = f"Generated {response.usage.completion_tokens} tokens"
            else:
                self.status = response_content

            return message

        except Exception as e:
            error_msg = self._get_exception_message(e) or str(e)
            self.status = f"Error: {error_msg}"
            raise ValueError(error_msg) from e

    def build_model(self) -> LanguageModel:
        """Build the ChatOpenAI model configured for Databricks endpoint.
        
        Always returns a LanguageModel instance. Authentication and validation
        errors are deferred to runtime when the model is actually invoked.
        """
        base_url = self._safe_str(self.base_url) or ""
        api_token = self._safe_str(self.api_token) or ""
        model_name = self._safe_str(self.model_name) or ""

        # Prepare parameters for ChatOpenAI
        # Use empty strings/None if not provided - let runtime handle validation
        parameters = {
            "api_key": api_token if api_token else None,
            "model": model_name if model_name else "databricks-meta-llama-3-1-8b-instruct",
            "base_url": base_url if base_url else "",
            "temperature": self.temperature if self.temperature is not None else 1.0,
            "max_tokens": self.max_tokens if self.max_tokens and self.max_tokens > 0 else None,
        }

        model = ChatOpenAI(**parameters)

        # Patch to remove max_completion_tokens from requests
        # Databricks API doesn't support max_completion_tokens, only max_tokens
        if hasattr(model, "client") and model.client:
            # Patch chat.completions.create
            if hasattr(model.client, "chat") and hasattr(model.client.chat, "completions"):
                original_create = model.client.chat.completions.create

                def patched_create(*args, **kwargs):
                    # Remove max_completion_tokens if present
                    kwargs.pop("max_completion_tokens", None)
                    # Also check in extra_body if it exists
                    if "extra_body" in kwargs and isinstance(kwargs["extra_body"], dict):
                        kwargs["extra_body"].pop("max_completion_tokens", None)
                    return original_create(*args, **kwargs)

                model.client.chat.completions.create = patched_create

        return model

    def _get_exception_message(self, e: Exception):
        """Get a message from a Databricks/OpenAI exception.

        Args:
            e (Exception): The exception to get the message from.

        Returns:
            str: The message from the exception.
        """
        try:
            from openai import BadRequestError
        except ImportError:
            return None
        if isinstance(e, BadRequestError):
            if isinstance(e.body, dict):
                message = e.body.get("message")
                if message:
                    return message
        return None
