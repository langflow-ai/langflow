from typing import Any

from langchain_gigachat import GigaChat

from lfx.base.constants import STREAM_INFO_TEXT
from lfx.base.models.gigachat_constants import GIGACHAT_CHAT_MODEL_NAMES, GIGACHAT_SCOPES
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import BoolInput, DropdownInput, FloatInput, IntInput, SecretStrInput, SliderInput, StrInput
from lfx.logging import logger


class GigaChatComponent(LCModelComponent):
    display_name = "GigaChat Language Model"
    description = "Generates text using GigaChat LLMs."
    icon = "GigaChat"
    name = "GigaChatModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        BoolInput(name="stream", display_name="Stream", info=STREAM_INFO_TEXT, advanced=False),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate.",
            range_spec=RangeSpec(min=0, max=128000),
        ),
        DropdownInput(
            name="model",
            display_name="Model Name",
            advanced=False,
            options=GIGACHAT_CHAT_MODEL_NAMES,
            value=GIGACHAT_CHAT_MODEL_NAMES[0],
            combobox=True,
        ),
        StrInput(
            name="base_url",
            display_name="GigaChat API Base",
            advanced=True,
            value=None,
            info="The base URL of the GigaChat API.",
        ),
        StrInput(
            name="auth_url",
            display_name="GigaChat Auth URL",
            advanced=True,
            value=None,
            info="The auth URL of the GigaChat API.",
        ),
        DropdownInput(
            name="scope",
            display_name="GigaChat Scope",
            advanced=False,
            options=GIGACHAT_SCOPES,
            value=GIGACHAT_SCOPES[0],
            info="Version of the API you are getting access to. "
            "You can find the value of the scope field in your profile after you create a project.",
            combobox=True,
        ),
        SecretStrInput(
            name="credentials",
            display_name="GigaChat Credentials",
            info="The GigaChat API Key to use for the GigaChat model.",
            advanced=False,
            value=None,
            required=False,
        ),
        StrInput(
            name="user",
            display_name="GigaChat User",
            info="The GigaChat API Username to use (if required by your authentication method).",
            advanced=True,
            value=None,
            required=False,
        ),
        SecretStrInput(
            name="password",
            display_name="GigaChat Password",
            info="The GigaChat API Password to use (if required by your authentication method).",
            advanced=True,
            value=None,
            required=False,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="The timeout for requests to GigaChat completion API.",
            advanced=True,
            value=700,
        ),
        BoolInput(
            name="profanity_check",
            display_name="profanity_check",
            value=True,
            advanced=True,
            info="Check for profanity",
        ),
        BoolInput(
            name="verify_ssl_certs",
            display_name="verify_ssl_certs",
            value=False,
            advanced=True,
            info="Check certificates for all requests ",
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=None,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            show=True,
        ),
        FloatInput(
            name="top_p",
            display_name="top_p",
            value=1,
            advanced=True,
        ),
        FloatInput(
            name="repetition_penalty",
            display_name="repetition_penalty",
            value=1,
            advanced=True,
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        logger.debug(f"Executing request with model: {self.model}")
        parameters: dict[str, Any] = {
            "credentials": self.credentials,
            "scope": self.scope,
            "model": self.model,
            "base_url": self.base_url,
            "auth_url": self.auth_url,
            "profanity_check": self.profanity_check,
            "user": self.user,
            "password": self.password,
            "timeout": self.timeout,
            "verify_ssl_certs": self.verify_ssl_certs,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "repetition_penalty": self.repetition_penalty,
        }
        return GigaChat(**parameters)
