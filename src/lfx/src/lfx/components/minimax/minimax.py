import requests
from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr
from typing_extensions import override

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import (
    BoolInput,
    DictInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    SecretStrInput,
    SliderInput,
)

MINIMAX_MODELS = ["MiniMax-M2.7", "MiniMax-M2.7-highspeed"]


class MiniMaxModelComponent(LCModelComponent):
    display_name = "MiniMax"
    description = "Generate text using MiniMax LLMs."
    icon = "MiniMax"
    name = "MiniMaxModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="Maximum number of tokens to generate. Set to 0 for unlimited.",
            range_spec=RangeSpec(min=0, max=128000),
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            advanced=True,
            info="Additional keyword arguments to pass to the model.",
        ),
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            advanced=True,
            info="If True, it will output JSON regardless of passing a schema.",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=MINIMAX_MODELS,
            value=MINIMAX_MODELS[0],
            refresh_button=True,
            combobox=True,
            info="The MiniMax model to use.",
        ),
        MessageTextInput(
            name="base_url",
            display_name="MiniMax API Base",
            advanced=True,
            info="The base URL of the MiniMax API. Defaults to https://api.minimax.io/v1",
            value="https://api.minimax.io/v1",
        ),
        SecretStrInput(
            name="api_key",
            display_name="MiniMax API Key",
            info="The MiniMax API Key to use for the model.",
            advanced=False,
            value="MINIMAX_API_KEY",
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=1.0,
            range_spec=RangeSpec(min=0.01, max=1.0, step=0.01),
            advanced=True,
            info="Controls randomness in responses. MiniMax requires a value in (0.0, 1.0].",
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="The seed controls the reproducibility of the job.",
            advanced=True,
            value=1,
        ),
    ]

    def get_models(self) -> list[str]:
        """Return the list of available MiniMax models."""
        if not self.api_key:
            return MINIMAX_MODELS

        base_url = self.base_url or "https://api.minimax.io/v1"
        url = f"{base_url}/models"
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            models = [model["id"] for model in data.get("data", [])]
            return models if models else MINIMAX_MODELS
        except requests.RequestException as e:
            self.status = f"Error fetching models: {e}"
            return MINIMAX_MODELS

    @override
    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Update build configuration with fresh model list when key fields change."""
        if field_name in {"api_key", "base_url", "model_name"}:
            models = self.get_models()
            build_config["model_name"]["options"] = models
        return build_config

    def build_model(self) -> LanguageModel:
        api_key = self.api_key
        temperature = self.temperature
        model_name: str = self.model_name
        max_tokens = self.max_tokens
        model_kwargs = self.model_kwargs or {}
        base_url = self.base_url or "https://api.minimax.io/v1"
        json_mode = self.json_mode
        seed = self.seed

        # MiniMax temperature must be in (0.0, 1.0], never 0
        if temperature is None or temperature <= 0:
            temperature = 1.0

        api_key = SecretStr(api_key).get_secret_value() if api_key else None

        output = ChatOpenAI(
            max_tokens=max_tokens or None,
            model_kwargs=model_kwargs,
            model=model_name,
            base_url=base_url,
            api_key=api_key,
            temperature=temperature,
            seed=seed,
        )

        if json_mode:
            output = output.bind(response_format={"type": "json_object"})

        return output

    def _get_exception_message(self, e: Exception):
        """Get a message from a MiniMax exception."""
        try:
            from openai import BadRequestError
        except ImportError:
            return None
        if isinstance(e, BadRequestError):
            message = e.body.get("message")
            if message:
                return message
        return None
