import requests
from langchain_openai import ChatOpenAI
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import (
    BoolInput,
    DictInput,
    DropdownInput,
    HandleInput,
    IntInput,
    SecretStrInput,
    SliderInput,
)
from pydantic.v1 import SecretStr
from typing_extensions import override

EMPIRIOLABS_BASE_URL = "https://api.empiriolabs.ai/v1"

EMPIRIOLABS_MODELS = [
    "qwen3-7-plus",
    "qwen3-7-max",
    "deepseek-v4-pro",
    "deepseek-v4-flash",
    "glm-5-1",
    "kimi-k2-7-code",
    "minimax-m3",
]
MODEL_NAMES = EMPIRIOLABS_MODELS  # reverse compatibility


class EmpirioLabsModelComponent(LCModelComponent):
    display_name = "EmpirioLabs AI"
    description = "Generates text using EmpirioLabs AI LLMs (OpenAI compatible)."
    icon = "EmpirioLabs"
    name = "EmpirioLabsModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
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
        ),
        SecretStrInput(
            name="api_key",
            display_name="EmpirioLabs API Key",
            info="The EmpirioLabs API Key to use for EmpirioLabs AI models.",
            advanced=False,
            value="EMPIRIOLABS_API_KEY",
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
        url = f"{EMPIRIOLABS_BASE_URL}/models"

        headers = {"Content-Type": "application/json"}
        api_key = getattr(self, "api_key", None)
        if api_key:
            token = SecretStr(api_key).get_secret_value() if isinstance(api_key, str) else api_key
            headers["Authorization"] = f"Bearer {token}"

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
                base_url=EMPIRIOLABS_BASE_URL,
            )
        except Exception as e:
            msg = "Could not connect to EmpirioLabs API."
            raise ValueError(msg) from e

        if json_mode:
            output = output.bind(response_format={"type": "json_object"})

        return output
