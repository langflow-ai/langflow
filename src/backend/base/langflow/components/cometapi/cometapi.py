import requests
from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr
from typing_extensions import override

from langflow.base.models.cometapi_constants import MODEL_NAMES
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import (
    BoolInput,
    DictInput,
    DropdownInput,
    IntInput,
    SecretStrInput,
    SliderInput,
)
from langflow.inputs.inputs import HandleInput


class CometAPIModelComponent(LCModelComponent):
    display_name = "CometAPI"
    description = "Generates text using CometAPI LLMs (OpenAI compatible)."
    icon = "CometAPI"
    name = "CometAPIModel"

    inputs = [
        *LCModelComponent._base_inputs,
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
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
            options=MODEL_NAMES,
            value=MODEL_NAMES[0],
            refresh_button=True,
            combobox=True,
            info="Select a model from the dropdown or enter a custom model name.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="CometAPI API Key",
            info="The CometAPI API Key to use for CometAPI models.",
            advanced=False,
            value="COMETAPI_API_KEY",
            real_time_refresh=True,
        ),
        SliderInput(name="temperature", display_name="Temperature", value=0.1, range_spec=RangeSpec(min=0, max=1)),
        IntInput(
            name="seed",
            display_name="Seed",
            info="The seed controls the reproducibility of the job.",
            advanced=True,
            value=1,
        ),
        HandleInput(
            name="output_parser",
            display_name="Output Parser",
            info="The parser to use to parse the output of the model",
            advanced=True,
            input_types=["OutputParser"],
        ),
    ]

    def get_models(self) -> list[str]:
        base_url = "https://api.cometapi.com/v1"
        url = f"{base_url}/models"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
        }

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
        model_kwargs = self.model_kwargs or {}
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
            msg = "Could not connect to CometAPI API."
            raise ValueError(msg) from e

        if json_mode:
            output = output.bind(response_format={"type": "json_object"})

        return output
