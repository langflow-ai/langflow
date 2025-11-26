from typing import Any

from langchain_community.chat_models import ChatOpenAI
from pydantic.v1 import SecretStr

from ...base.models.model import LCModelComponent
from ...field_typing import LanguageModel
from ...field_typing.range_spec import RangeSpec
from ...inputs import BoolInput, DictInput, DropdownInput, IntInput, SecretStrInput, SliderInput, StrInput
from ...log import logger


class BailingChatModel(LCModelComponent):
    display_name = "Bailing Model"
    description = "Generate text using Bailing large model"
    icon = "Bailing"
    name = "BailingModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="Maximum number of tokens to generate. Set to 0 for no limit.",
            range_spec=RangeSpec(min=0, max=128000),
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Parameters",
            advanced=True,
            info="Additional keyword arguments to pass to the model.",
        ),
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            advanced=True,
            info="If True, will output JSON regardless of whether a schema is passed.",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=["Ling-1T", "Ring-1T"],
            value="Ling-1T",
            combobox=True,
            real_time_refresh=True,
        ),
        StrInput(
            name="bailing_api_base",
            display_name="Bailing API Base URL",
            advanced=True,
            info="Base URL for the Bailing API.",
            value="https://api.tbox.cn/api/llm/v1/chat/completions",
        ),
        SecretStrInput(
            name="api_key",
            display_name="Bailing API Key",
            info="API key for the Bailing model.",
            advanced=False,
            value="DASHSCOPE_API_KEY",
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
            info="Seed for controlling reproducibility of the job.",
            advanced=True,
            value=1,
        ),
        IntInput(
            name="max_retries",
            display_name="Max Retries",
            info="Maximum number of retries when generating.",
            advanced=True,
            value=3,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout for Bailing to complete API requests.",
            advanced=True,
            value=600,
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        logger.debug(f"Using model to execute request: {self.model_name}")
        # Process api_key - it can be a string or SecretStr
        api_key_value = None
        if self.api_key:
            logger.debug(f"API key type: {type(self.api_key)}, value: {self.api_key!r}")
            if isinstance(self.api_key, SecretStr):
                api_key_value = self.api_key.get_secret_value()
            else:
                api_key_value = str(self.api_key)
        logger.debug(f"Final api_key_value type: {type(api_key_value)}, value: {'***' if api_key_value else None}")

        # Process model_kwargs and ensure api_key doesn't conflict
        model_kwargs = self.model_kwargs or {}
        # Remove api_key from model_kwargs (if present) to prevent conflicts
        if "api_key" in model_kwargs:
            logger.warning("Found api_key in model_kwargs, removing to prevent conflicts")
            model_kwargs = dict(model_kwargs)  # Create a copy
            del model_kwargs["api_key"]

        parameters = {
            "api_key": api_key_value,
            "model_name": self.model_name,
            "max_tokens": self.max_tokens or None,
            "model_kwargs": model_kwargs,
            "base_url": self.bailing_api_base or "https://api.tbox.cn/api/llm/v1/chat/completions",
            "max_retries": self.max_retries,
            "timeout": self.timeout,
        }

        # Add temperature and seed parameters
        parameters["temperature"] = self.temperature if self.temperature is not None else 0.7
        parameters["seed"] = self.seed

        # Ensure all parameter values are of the correct type
        if isinstance(parameters.get("api_key"), SecretStr):
            parameters["api_key"] = parameters["api_key"].get_secret_value()
        output = ChatOpenAI(**parameters)
        if self.json_mode:
            output = output.bind(response_format={"type": "json_object"})

        return output

    def _get_exception_message(self, e: Exception):
        """Get message from Bailing exception.

        Args:
            e (Exception): Exception to get message from.

        Returns:
            str: Message from the exception.
        """
        try:
            from openai import BadRequestError
        except ImportError:
            return None
        if isinstance(e, BadRequestError):
            message = e.body.get("message")
            if message:
                return message
        return None

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        return build_config
