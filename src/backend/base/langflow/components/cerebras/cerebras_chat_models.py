from typing import Any

# from langchain_openai import ChatOpenAI
from langchain_cerebras import ChatCerebras
from pydantic.v1 import SecretStr

from langflow.base.models.cerebras_constants import (
    CEREBRAS_CHAT_MODEL_NAMES,
    CEREBRAS_REASONING_MODEL_NAMES,
)
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs.inputs import BoolInput, DictInput, DropdownInput, IntInput, SecretStrInput, SliderInput, StrInput
from langflow.logging import logger


class CerebrasModelComponent(LCModelComponent):
    display_name = "🧠 Cerebras"
    description = "Generates text using Cerebras LLMs."
    icon = "🧠"
    name = "CerebrasModel"

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
            options=CEREBRAS_CHAT_MODEL_NAMES + CEREBRAS_REASONING_MODEL_NAMES,
            value=CEREBRAS_CHAT_MODEL_NAMES[0],
            combobox=True,
            real_time_refresh=True,
        ),
        StrInput(
            name="Cerebras_api_base",
            display_name="Cerebras API Base",
            advanced=True,
            info="The base URL of the Cerebras API. "
            "Defaults to https://api.cerebras.ai/v1. "
            "You can change this to use other APIs like JinaChat, LocalAI and Prem.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="Cerebras API Key",
            info="The Cerebras API Key to use for the Cerebras model.",
            advanced=False,
            value="CEREBRAS_API_KEY",
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
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
            info="The timeout for requests to Cerebras completion API.",
            advanced=True,
            value=700,
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        logger.debug(f"Executing request with model: {self.model_name}")
        parameters = {
            "api_key": SecretStr(self.api_key).get_secret_value() if self.api_key else None,
            "model_name": self.model_name,
            "max_tokens": self.max_tokens or None,
            "model_kwargs": self.model_kwargs or {},
            "base_url": "https://api.cerebras.ai/v1",
            "max_retries": self.max_retries,
            "timeout": self.timeout,
        }

        # TODO: Revisit if/once parameters are supported for reasoning models
        unsupported_params_for_reasoning_models = ["temperature", "seed"]

        if self.model_name not in CEREBRAS_REASONING_MODEL_NAMES:
            parameters["temperature"] = self.temperature if self.temperature is not None else 0.1
            parameters["seed"] = self.seed
        else:
            params_str = ", ".join(unsupported_params_for_reasoning_models)
            logger.debug(f"{self.model_name} is a reasoning model, {params_str} are not configurable. Ignoring.")

        output = ChatCerebras(**parameters)
        if self.json_mode:
            output = output.bind(response_format={"type": "json_object"})

        return output

    def _get_exception_message(self, e: Exception):
        """Get a message from an Cerebras exception.

        Args:
            e (Exception): The exception to get the message from.

        Returns:
            str: The message from the exception.
        """
        try:
            from cerebras import BadRequestError
        except ImportError:
            return None
        if isinstance(e, BadRequestError):
            message = e.body.get("message")
            if message:
                return message
        return None

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        if field_name in {"base_url", "model_name", "api_key"} and field_value in CEREBRAS_REASONING_MODEL_NAMES:
            build_config["temperature"]["show"] = False
            build_config["seed"]["show"] = False
            # Hide system_message for o1 models - currently unsupported
            if field_value.startswith("o1") and "system_message" in build_config:
                build_config["system_message"]["show"] = False
        if field_name in {"base_url", "model_name", "api_key"} and field_value in CEREBRAS_CHAT_MODEL_NAMES:
            build_config["temperature"]["show"] = True
            build_config["seed"]["show"] = True
            if "system_message" in build_config:
                build_config["system_message"]["show"] = True
        return build_config
