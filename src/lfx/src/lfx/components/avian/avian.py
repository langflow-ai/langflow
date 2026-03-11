import requests
from pydantic.v1 import SecretStr
from typing_extensions import override

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DictInput, DropdownInput, IntInput, SecretStrInput, SliderInput, StrInput

AVIAN_DEFAULT_MODELS = [
    "deepseek/deepseek-v3.2",
    "moonshotai/kimi-k2.5",
    "z-ai/glm-5",
    "minimax/minimax-m2.5",
]


class AvianModelComponent(LCModelComponent):
    display_name = "Avian"
    description = "Generate text using Avian LLMs."
    icon = "Bird"
    name = "AvianModel"

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
            info="Avian model to use.",
            options=AVIAN_DEFAULT_MODELS,
            value=AVIAN_DEFAULT_MODELS[0],
            refresh_button=True,
        ),
        StrInput(
            name="api_base",
            display_name="Avian API Base",
            advanced=True,
            info="Base URL for API requests. Defaults to https://api.avian.io/v1",
            value="https://api.avian.io/v1",
        ),
        SecretStrInput(
            name="api_key",
            display_name="Avian API Key",
            info="The Avian API Key.",
            advanced=False,
            value="AVIAN_API_KEY",
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            info="Controls randomness in responses.",
            value=0.7,
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
        """Fetch available models from the Avian API.

        Returns the list of model IDs from the API, or falls back to
        AVIAN_DEFAULT_MODELS if the API key is missing or the request fails.
        """
        if not self.api_key:
            return AVIAN_DEFAULT_MODELS

        url = f"{self.api_base}/models"
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            model_list = response.json()
            data = model_list.get("data", []) if isinstance(model_list, dict) else []
            models = [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]
            return models or AVIAN_DEFAULT_MODELS
        except (requests.RequestException, ValueError, TypeError) as e:
            self.status = f"Error fetching models: {e}"
            return AVIAN_DEFAULT_MODELS

    @override
    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Update the build configuration when API credentials or model selection change."""
        if field_name in {"api_key", "api_base", "model_name"}:
            models = self.get_models()
            build_config["model_name"]["options"] = models
        return build_config

    def build_model(self) -> LanguageModel:
        """Build a ChatOpenAI model configured for the Avian API."""
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            msg = "langchain-openai not installed. Please install with `pip install langchain-openai`"
            raise ImportError(msg) from e

        api_key = SecretStr(self.api_key).get_secret_value() if self.api_key else None
        output = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature if self.temperature is not None else 0.7,
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
        """Get message from Avian API exception.

        Safely handles OpenAI BadRequestError where e.body may be a dict,
        string, or None. Falls back to the base class implementation.
        """
        try:
            from openai import BadRequestError

            if isinstance(e, BadRequestError):
                body = getattr(e, "body", None)
                if isinstance(body, dict):
                    message = body.get("message")
                    if message:
                        return message
        except ImportError:
            pass
        return super()._get_exception_message(e)
