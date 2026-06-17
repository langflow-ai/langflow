import requests
from pydantic.v1 import SecretStr
from typing_extensions import override

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DictInput, DropdownInput, IntInput, SecretStrInput, SliderInput, StrInput

# A curated subset of the Atlas Cloud OpenAI-compatible chat models. The full,
# up-to-date catalog is fetched at runtime via ``get_models`` when an API key is
# provided. See https://www.atlascloud.ai/models for the complete list.
ATLASCLOUD_MODELS = [
    "deepseek-ai/deepseek-v4-pro",
    "deepseek-ai/deepseek-v4-flash",
    "deepseek-ai/deepseek-v3.2",
    "anthropic/claude-sonnet-4.6",
    "anthropic/claude-opus-4.8",
    "openai/gpt-5.5",
    "google/gemini-3.5-flash",
    "qwen/qwen3.6-plus",
    "moonshotai/kimi-k2.6",
    "zai-org/glm-5",
    "minimaxai/minimax-m2.7",
    "xai/grok-4.3",
]


class AtlasCloudModelComponent(LCModelComponent):
    display_name = "Atlas Cloud"
    description = "Generate text using Atlas Cloud LLMs (OpenAI-compatible)."
    icon = "bot"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info=(
                "Maximum number of tokens to generate. Set to 0 for unlimited. "
                "Reasoning models such as deepseek-v4-pro need enough room (>= 512) "
                "or the response may be empty with finish_reason=length."
            ),
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
            info="Atlas Cloud model to use",
            options=ATLASCLOUD_MODELS,
            value="deepseek-ai/deepseek-v4-pro",
            refresh_button=True,
        ),
        StrInput(
            name="api_base",
            display_name="Atlas Cloud API Base",
            advanced=True,
            info="Base URL for API requests. Defaults to https://api.atlascloud.ai/v1",
            value="https://api.atlascloud.ai/v1",
        ),
        SecretStrInput(
            name="api_key",
            display_name="Atlas Cloud API Key",
            info="The Atlas Cloud API Key",
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
            return ATLASCLOUD_MODELS

        url = f"{self.api_base}/models"
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            model_list = response.json()
            return [model["id"] for model in model_list.get("data", [])]
        except requests.RequestException as e:
            self.status = f"Error fetching models: {e}"
            return ATLASCLOUD_MODELS

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
        """Get message from Atlas Cloud API exception."""
        try:
            from openai import BadRequestError

            if isinstance(e, BadRequestError):
                message = e.body.get("message")
                if message:
                    return message
        except ImportError:
            pass
        return None
