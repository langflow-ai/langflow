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
        SecretStrInput(name="api_key", display_name="CometAPI Key", required=True, info="Your CometAPI key"),
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

    def get_models(self) -> list[str]:
        base_url = "https://api.cometapi.com/v1"
        url = f"{base_url}/models"

        headers = {"Content-Type": "application/json"}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            model_list = response.json()
            return [model["id"] for model in model_list.get("data", [])]
        except requests.RequestException as e:
            self.status = f"Error fetching models: {e}"
            return MODEL_NAMES

    @override
    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        if field_name in {"api_key", "model_name"}:
            models = self.get_models()
            build_config["model_name"]["options"] = models
        return build_config

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        api_key = self.api_key
        temperature = self.temperature
        model_name: str = self.model_name
        max_tokens = self.max_tokens
        model_kwargs = getattr(self, "model_kwargs", {}) or {}
        json_mode = self.json_mode
        seed = self.seed

        try:
            output = ChatOpenAI(
                model=model_name,
                api_key=(SecretStr(api_key).get_secret_value() if api_key else None),
                max_tokens=max_tokens or None,
                temperature=temperature,
                model_kwargs=model_kwargs,
                streaming=self.stream,
                seed=seed,
                base_url="https://api.cometapi.com/v1",
            )
        except Exception as e:
            msg = "Could not connect to CometAPI."
            raise ValueError(msg) from e

        if json_mode:
            output = output.bind(response_format={"type": "json_object"})

        return output
