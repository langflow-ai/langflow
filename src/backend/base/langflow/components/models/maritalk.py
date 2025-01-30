from http import HTTPStatus
from typing import Any

import requests
from langchain_community.chat_models import ChatMaritalk

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput, StrInput

# Constants
DEFAULT_MODELS = ["sabiazinho-3", "sabia-3"]
MARITACA_API_URL = "https://chat.maritaca.ai/api/models"
REQUEST_TIMEOUT = 5


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
            info="Select a Maritaca model or choose 'custom' to specify your own",
            options=[*DEFAULT_MODELS, "custom"],
            value=DEFAULT_MODELS[0],
            required=True,
            real_time_refresh=True,
        ),
        StrInput(
            name="custom_model",
            display_name="Custom Model Name",
            info="Enter a custom model name if you selected 'custom' in Model Name",
            value="",
            show=False,
            required=True,
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
            return DEFAULT_MODELS

        try:
            response = requests.get(
                MARITACA_API_URL,
                headers={"Authorization": f"Key {self.api_key}"},
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code != HTTPStatus.OK:
                return DEFAULT_MODELS

            data = response.json()
            models = data.get("data", [])
            # Sort models by creation date (newest first)
            sorted_models = sorted(models, key=lambda x: x.get("created", 0), reverse=True)
            return [model["id"] for model in sorted_models]
        except requests.RequestException:
            return DEFAULT_MODELS

    async def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Update build configuration based on field updates."""
        try:
            # Update model list on initialization or when API key changes
            if field_name is None or field_name == "api_key":
                models = self.fetch_models()
                if hasattr(self, "api_key") and self.api_key:
                    # If we have an API key, add custom option to API models
                    models = [*models, "custom"]
                else:
                    # If no API key, use default models + custom
                    models = [*DEFAULT_MODELS, "custom"]

                build_config["model_name"]["options"] = models
                if build_config["model_name"]["value"] not in models:
                    build_config["model_name"]["value"] = models[0]

            # Handle custom model field visibility
            if field_name is None or field_name == "model_name":
                if field_value == "custom":
                    build_config["custom_model"]["show"] = True
                    build_config["custom_model"]["required"] = True
                else:
                    build_config["custom_model"]["show"] = False
                    build_config["custom_model"]["value"] = ""
                    build_config["custom_model"]["required"] = False

        except (KeyError, AttributeError):
            return build_config
        return build_config

    def build_model(self) -> LanguageModel:
        api_key = self.api_key
        temperature = self.temperature
        model_name = self.custom_model if self.model_name == "custom" else self.model_name
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
