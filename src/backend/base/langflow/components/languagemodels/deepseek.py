import requests
from pydantic.v1 import SecretStr
from typing_extensions import override

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import BoolInput, DictInput, DropdownInput, IntInput, SecretStrInput, SliderInput, StrInput

DEEPSEEK_MODELS = ["deepseek-chat"]


class DeepSeekModelComponent(LCModelComponent):
    display_name = "DeepSeek"
    description = "Generate text using DeepSeek LLMs."
    icon = "DeepSeek"

    inputs = [
        *LCModelComponent._base_inputs,
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
            info="DeepSeek model to use",
            options=DEEPSEEK_MODELS,
            value="deepseek-chat",
            refresh_button=True,
        ),
        StrInput(
            name="api_base",
            display_name="DeepSeek API Base",
            advanced=True,
            info="Base URL for API requests. Defaults to https://api.deepseek.com",
            value="https://api.deepseek.com",
        ),
        SecretStrInput(
            name="api_key",
            display_name="DeepSeek API Key",
            info="The DeepSeek API Key",
            advanced=False,
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            info="Controls randomness in responses",
            value=1.0,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            advanced=True,
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
        if not self.api_key:
            return DEEPSEEK_MODELS

        url = f"{self.api_base}/models"
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            model_list = response.json()
            return [model["id"] for model in model_list.get("data", [])]
        except requests.RequestException as e:
            self.status = f"Error fetching models: {e}"
            return DEEPSEEK_MODELS

    @override
    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        if field_name in {"api_key", "api_base", "model_name"}:
            models = self.get_models()
            build_config["model_name"]["options"] = models
        return build_config

    def build_model(self) -> LanguageModel:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            msg = "langchain-openai not installed. Please install with `pip install langchain-openai`"
            raise ImportError(msg) from e

        api_key = SecretStr(self.api_key).get_secret_value() if self.api_key else None
        output = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature if self.temperature is not None else 0.1,
            max_tokens=self.max_tokens or None,
            model_kwargs=self.model_kwargs or {},
            base_url=self.api_base,
            api_key=api_key,
            streaming=self.stream if hasattr(self, "stream") else False,
            seed=self.seed,
        )

        if self.json_mode:
            output = output.bind(response_format={"type": "json_object"})

        return output

    def _get_exception_message(self, e: Exception):
        """Get message from DeepSeek API exception."""
        try:
            from openai import BadRequestError

            if isinstance(e, BadRequestError):
                message = e.body.get("message")
                if message:
                    return message
        except ImportError:
            pass
        return None
