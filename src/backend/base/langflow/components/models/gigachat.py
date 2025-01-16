from pydantic.v1 import SecretStr

from langflow.base.models.gigachat_constants import GIGACHAT_MODEL_NAMES
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput, StrInput


class GigaChatComponent(LCModelComponent):
    display_name = "GigaChat"
    description = "Generates text using LLM GigaChat"
    icon = "GigaChat"

    inputs = [
        *LCModelComponent._base_inputs,
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
            range_spec=RangeSpec(min=0, max=32000),
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=GIGACHAT_MODEL_NAMES,
            value=GIGACHAT_MODEL_NAMES[0],
        ),
        StrInput(
            name="gigachat_api_base",
            display_name="GigaChat API Base",
            advanced=True,
            info="The base URL of the GigaChat API. ",
        ),
        SecretStrInput(
            name="gigachat_credentials",
            display_name="GigaChat credentials",
            info="GigaChat credentials",
            advanced=False,
            value="GIGACHAT_CREDENTIALS",
        ),
        StrInput(
            name="gigachat_user",
            display_name="GigaChat User",
            advanced=True,
            info="GigaChat user",
        ),
        SecretStrInput(
            name="password",
            display_name="GigaChat password",
            info="GigaChat password",
            advanced=True,
            value="GIGACHAT_PASSWORD",
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        try:
            from langchain_gigachat import GigaChat
        except ImportError:
            msg = "GigaChat is not installed. Please install it with `pip install langchain-gigachat`."
            raise ImportError(msg) from None
        gigachat_credentials = self.gigachat_credentials
        temperature = self.temperature
        model_name: str = self.model_name
        max_tokens = self.max_tokens
        gigachat_user = self.gigachat_user
        password = self.password
        gigachat_api_base = self.gigachat_api_base or None

        gigachat_credentials = SecretStr(gigachat_credentials).get_secret_value() if gigachat_credentials else None
        return GigaChat(
            credentials=gigachat_credentials,
            user=gigachat_user or None,
            password=password or None,
            max_tokens=max_tokens or None,
            model=model_name,
            base_url=gigachat_api_base,
            temperature=temperature if temperature is not None else 1.0,
            verify_ssl_certs=False,
        )

    def _get_exception_message(self, e: Exception):
        """Get a message from an GigaChat exception.

        Args:
            e (Exception): The exception to get the message from.

        Returns:
            str: The message from the exception.
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
