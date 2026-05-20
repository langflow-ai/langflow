from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from lfx.base.models.model import LCModelComponent
from lfx.components.regolo.regolo_constants import REGOLO_CHAT_MODEL_NAMES
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput, SliderInput, StrInput
from lfx.log.logger import logger


class RegoloModelComponent(LCModelComponent):
    display_name = "Regolo.ai"
    description = "Generates text using Regolo.ai LLMs."
    icon = "Regolo"
    name = "RegoloModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        StrInput(
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
            options=REGOLO_CHAT_MODEL_NAMES,
            value=REGOLO_CHAT_MODEL_NAMES[0] if REGOLO_CHAT_MODEL_NAMES else "Llama-3.1-8B-Instruct",
            combobox=True,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="regolo_api_base",
            display_name="Regolo API Base",
            advanced=True,
            info=(
                "The base URL of the Regolo API. "
                "Defaults to https://api.regolo.ai/v1. "
                "You can change this to use a proxy or self-hosted Regolo instance."
            ),
            value="https://api.regolo.ai/v1",
        ),
        SecretStrInput(
            name="api_key",
            display_name="Regolo API Key",
            info="The Regolo API Key to use for the Regolo model.",
            advanced=False,
            value="REGOLO_API_KEY",
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            show=True,
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="The seed controls the reproducibility of the job.",
            advanced=True,
            value=1,
        ),
        IntInput(
            name="max_retries",
            display_name="Max Retries",
            info="The maximum number of retries to make when generating.",
            advanced=True,
            value=5,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="The timeout for requests to Regolo API.",
            advanced=True,
            value=700,
        ),
    ]

    def build_model(self) -> LanguageModel:
        logger.debug(f"Executing request with model: {self.model_name}")

        # Handle api_key - it can be string or SecretStr
        api_key_value = None
        if self.api_key:
            logger.debug(f"API key type: {type(self.api_key)}, value: {'***' if self.api_key else None}")
            if isinstance(self.api_key, SecretStr):
                api_key_value = self.api_key.get_secret_value()
            else:
                api_key_value = str(self.api_key)
        logger.debug(f"Final api_key_value type: {type(api_key_value)}, value: {'***' if api_key_value else None}")

        model_kwargs = {}
        if self.model_kwargs:
            import json

            try:
                model_kwargs = json.loads(self.model_kwargs)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in model_kwargs: {self.model_kwargs}")
                model_kwargs = {}

        parameters = {
            "api_key": api_key_value,
            "model": self.model_name,
            "max_tokens": self.max_tokens or None,
            "model_kwargs": model_kwargs,
            "base_url": self.regolo_api_base or "https://api.regolo.ai/v1",
            "max_retries": self.max_retries,
            "timeout": self.timeout,
        }

        # Add temperature (standard OpenAI parameter)
        parameters["temperature"] = self.temperature if self.temperature is not None else 0.7

        # Add stream_usage for better token tracking
        parameters["stream_usage"] = True

        output = ChatOpenAI(**parameters)

        if self.json_mode:
            output = output.bind(response_format={"type": "json_object"})

        return output

    def _get_exception_message(self, e: Exception):
        """Get a message from a Regolo.ai exception.

        Args:
            e (Exception): The exception to get the message from.

        Returns:
            str: The message from the exception.
        """
        try:
            from openai import BadRequestError, NotFoundError
        except ImportError:
            return None

        if isinstance(e, NotFoundError):
            body = getattr(e, "body", None) or {}
            if isinstance(body, dict) and body.get("code") == "model_not_found":
                return (
                    f"Model '{self.model_name}' is not available for this Regolo account. "
                    "Check your API key permissions or select a different model."
                )
        if isinstance(e, BadRequestError):
            message = e.body.get("message") if isinstance(e.body, dict) else str(e.body)
            if message:
                return message
        return None

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        if field_name in {"base_url", "model_name", "api_key"}:
            build_config["temperature"]["show"] = True
            build_config["seed"]["show"] = True
            if "system_message" in build_config:
                build_config["system_message"]["show"] = True
        return build_config
