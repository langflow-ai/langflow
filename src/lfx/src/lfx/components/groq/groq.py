import requests
from pydantic.v1 import SecretStr

from lfx.base.models.groq_constants import GROQ_MODELS, TOOL_CALLING_UNSUPPORTED_GROQ_MODELS, UNSUPPORTED_GROQ_MODELS
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput, SliderInput
from lfx.log.logger import logger


class GroqModel(LCModelComponent):
    display_name: str = "Groq"
    description: str = "Generate text using Groq."
    icon = "Groq"
    name = "GroqModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(
            name="api_key", display_name="Groq API Key", info="API key for the Groq API.", real_time_refresh=True
        ),
        MessageTextInput(
            name="base_url",
            display_name="Groq API Base",
            info="Base URL path for API requests, leave blank if not using a proxy or service emulator.",
            advanced=True,
            value="https://api.groq.com",
            real_time_refresh=True,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Output Tokens",
            info="The maximum number of tokens to generate.",
            advanced=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            info="Run inference with this temperature. Must by in the closed interval [0.0, 1.0].",
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
        ),
        IntInput(
            name="n",
            display_name="N",
            info="Number of chat completions to generate for each prompt. "
            "Note that the API may not return the full n completions if duplicates are generated.",
            advanced=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="The name of the model to use.",
            options=GROQ_MODELS,
            value=GROQ_MODELS[0],
            refresh_button=True,
            combobox=True,
        ),
        BoolInput(
            name="tool_model_enabled",
            display_name="Enable Tool Models",
            info=(
                "Select if you want to use models that can work with tools. If yes, only those models will be shown."
            ),
            advanced=False,
            value=False,
            real_time_refresh=True,
        ),
    ]

    def get_models(self, *, tool_model_enabled: bool | None = None) -> list[str]:
        try:
            url = f"{self.base_url}/openai/v1/models"
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            model_list = response.json()
            model_ids = [
                model["id"] for model in model_list.get("data", []) if model["id"] not in UNSUPPORTED_GROQ_MODELS
            ]
        except (ImportError, ValueError, requests.exceptions.RequestException) as e:
            logger.exception(f"Error getting model names: {e}")
            model_ids = GROQ_MODELS
        if tool_model_enabled:
            try:
                from langchain_groq import ChatGroq
            except ImportError as e:
                msg = "langchain_groq is not installed. Please install it with `pip install langchain_groq`."
                raise ImportError(msg) from e
            for model in model_ids:
                model_with_tool = ChatGroq(
                    model=model,
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
                if not self.supports_tool_calling(model_with_tool) or model in TOOL_CALLING_UNSUPPORTED_GROQ_MODELS:
                    model_ids.remove(model)
            return model_ids
        return model_ids

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        if field_name in {"base_url", "model_name", "tool_model_enabled", "api_key"} and field_value:
            try:
                if len(self.api_key) != 0:
                    try:
                        ids = self.get_models(tool_model_enabled=self.tool_model_enabled)
                    except (ImportError, ValueError, requests.exceptions.RequestException) as e:
                        logger.exception(f"Error getting model names: {e}")
                        ids = GROQ_MODELS
                    build_config.setdefault("model_name", {})
                    build_config["model_name"]["options"] = ids
                    build_config["model_name"].setdefault("value", ids[0])
            except Exception as e:
                msg = f"Error getting model names: {e}"
                raise ValueError(msg) from e
        return build_config

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        try:
            from langchain_groq import ChatGroq
        except ImportError as e:
            msg = "langchain-groq is not installed. Please install it with `pip install langchain-groq`."
            raise ImportError(msg) from e

        return ChatGroq(
            model=self.model_name,
            max_tokens=self.max_tokens or None,
            temperature=self.temperature,
            base_url=self.base_url,
            n=self.n or 1,
            api_key=SecretStr(self.api_key).get_secret_value(),
            streaming=self.stream,
        )
