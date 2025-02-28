from http import HTTPStatus
from typing import Any

import requests
from langchain_community.chat_models import ChatMaritalk

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput

# Constants
MARITACA_API_URL = "https://chat.maritaca.ai/api/models"
REQUEST_TIMEOUT = 5
MODEL_NAME_REQUIRED = "Model name is required"
DEFAULT_MODELS = ["sabiazinho-3", "sabia-3"]  # Default models as fallback


class MaritalkModelComponent(LCModelComponent):
    display_name = "Maritalk"
    description = "Generates text using Maritalk LLMs."
    icon = "Maritalk"
    name = "Maritalk"

    inputs = [
        *LCModelComponent._base_inputs,
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            value=512,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            info="Choose a model from the available options or type a custom model name.",
            options=DEFAULT_MODELS,  # Use default models initially
            required=True,
            real_time_refresh=True,
            combobox=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Maritalk API Key",
            info="The Maritalk API Key to use for the model.",
            required=True,
            real_time_refresh=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            info="Run inference with this temperature. Must by in the closed interval [0.0, 0.99].",
            range_spec=RangeSpec(min=0.0, max=0.99, step=0.01),
        ),
    ]

    def fetch_models(self) -> list[str]:
        """Fetch available models from Maritaca API."""
        if not hasattr(self, "api_key") or not self.api_key:
            return DEFAULT_MODELS  # Return default models if no API key is provided

        try:
            response = requests.get(
                MARITACA_API_URL,
                headers={"Authorization": f"Key {self.api_key}"},
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code != HTTPStatus.OK:
                self.log(f"Failed to fetch models: HTTP {response.status_code}", "maritalk_api_error")
                return DEFAULT_MODELS  # Return default models on API error

            data = response.json()
            models = data.get("data", [])
            # Sort models by creation date (newest first)
            sorted_models = sorted(models, key=lambda x: x.get("created", 0), reverse=True)
            model_ids = [model["id"] for model in sorted_models]
        except requests.RequestException as e:
            self.log(f"Error fetching models: {e!s}", "maritalk_api_error")
            return DEFAULT_MODELS  # Return default models on request exception
        else:
            # If no models were returned from the API, use default models
            return model_ids if model_ids else DEFAULT_MODELS

    async def update_build_config(self, build_config: dict, _: Any, field_name: str | None = None) -> dict:
        """Update build configuration based on field updates."""
        try:
            # Update model list on initialization or when API key changes
            if field_name is None or field_name == "api_key":
                models = self.fetch_models()

                # Always ensure we have at least the default models in the list
                unique_models = list(set(models + DEFAULT_MODELS))
                build_config["model_name"]["options"] = unique_models

                # Only set default value if current value is empty or invalid
                if not build_config["model_name"]["value"] or build_config["model_name"]["value"] not in unique_models:
                    build_config["model_name"]["value"] = unique_models[0] if unique_models else DEFAULT_MODELS[0]

        except (KeyError, AttributeError) as e:
            self.log(f"Error updating build config: {e!s}", "maritalk_config_error")
            # Ensure defaults are set even on error
            build_config["model_name"]["options"] = DEFAULT_MODELS
            build_config["model_name"]["value"] = DEFAULT_MODELS[0]

        return build_config

    def build_model(self) -> LanguageModel:
        if not self.model_name:
            raise ValueError(MODEL_NAME_REQUIRED)

        api_key = self.api_key
        temperature = self.temperature
        model_name = self.model_name
        max_tokens = self.max_tokens
        system_message = self.system_message

        self.log(f"Building Maritalk model: {model_name}", "maritalk_build")

        return ChatMaritalk(
            max_tokens=max_tokens,
            model=model_name,
            api_key=api_key,
            temperature=temperature or 0.1,
            system_message=system_message,
        )
