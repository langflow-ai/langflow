import json

import requests
from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr
from typing_extensions import override

from lfx.base.models.cometapi_constants import MODEL_NAMES
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import (
    BoolInput,
    DictInput,
    DropdownInput,
    IntInput,
    SecretStrInput,
    SliderInput,
    StrInput,
)


class CometAPIComponent(LCModelComponent):
    """CometAPI component for language models."""

    display_name = "CometAPI"
    description = "All AI Models in One API 500+ AI Models"
    icon = "CometAPI"
    name = "CometAPIModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(
            name="api_key",
            display_name="CometAPI Key",
            required=True,
            info="Your CometAPI key",
            real_time_refresh=True,
        ),
        StrInput(
            name="app_name",
            display_name="App Name",
            info="Your app name for CometAPI rankings",
            advanced=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="The model to use for chat completion",
            options=["Select a model"],
            value="Select a model",
            real_time_refresh=True,
            required=True,
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            info="Additional keyword arguments to pass to the model.",
            advanced=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            info="Controls randomness. Lower values are more deterministic, higher values are more creative.",
            advanced=True,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            info="Maximum number of tokens to generate",
            advanced=True,
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="Seed for reproducible outputs.",
            value=1,
            advanced=True,
        ),
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            info="If enabled, the model will be asked to return a JSON object.",
            advanced=True,
        ),
    ]

    def get_models(self, token_override: str | None = None) -> list[str]:
        base_url = "https://api.cometapi.com/v1"
        url = f"{base_url}/models"

        headers = {"Content-Type": "application/json"}
        # Add Bearer Authorization when API key is available
        api_key_source = token_override if token_override else getattr(self, "api_key", None)
        if api_key_source:
            token = api_key_source.get_secret_value() if isinstance(api_key_source, SecretStr) else str(api_key_source)
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            # Safely parse JSON; fallback to defaults on failure
            try:
                model_list = response.json()
            except (json.JSONDecodeError, ValueError) as e:
                self.status = f"Error decoding models response: {e}"
                return MODEL_NAMES
            return [model["id"] for model in model_list.get("data", [])]
        except requests.RequestException as e:
            self.status = f"Error fetching models: {e}"
            return MODEL_NAMES

    @override
    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        if field_name == "api_key":
            models = self.get_models(field_value)
            model_cfg = build_config.get("model_name", {})
            # Preserve placeholder (fallback to existing value or a generic prompt)
            placeholder = model_cfg.get("placeholder", model_cfg.get("value", "Select a model"))
            current_value = model_cfg.get("value")

            options = list(models) if models else []
            # Ensure current value stays visible even if not present in fetched options
            if current_value and current_value not in options:
                options = [current_value, *options]

            model_cfg["options"] = options
            model_cfg["placeholder"] = placeholder
            build_config["model_name"] = model_cfg
        return build_config

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        api_key = self.api_key
        temperature = self.temperature
        model_name: str = self.model_name
        max_tokens = self.max_tokens
        model_kwargs = getattr(self, "model_kwargs", {}) or {}
        json_mode = self.json_mode
        seed = self.seed
        # Ensure a valid model was selected
        if not model_name or model_name == "Select a model":
            msg = "Please select a valid CometAPI model."
            raise ValueError(msg)
        try:
            # Extract raw API key safely
            _api_key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
            output = ChatOpenAI(
                model=model_name,
                api_key=_api_key or None,
                max_tokens=max_tokens or None,
                temperature=temperature,
                model_kwargs=model_kwargs,
                streaming=bool(self.stream),
                seed=seed,
                base_url="https://api.cometapi.com/v1",
            )
        except (TypeError, ValueError) as e:
            msg = "Could not connect to CometAPI."
            raise ValueError(msg) from e

        if json_mode:
            output = output.bind(response_format={"type": "json_object"})

        return output
