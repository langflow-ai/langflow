import os

from langchain_sambanova import ChatSambaNova
from lfx.base.models.model import LCModelComponent
from lfx.base.models.provider_ssrf import ensure_credential_endpoint_allowed, openai_compatible_client_kwargs
from lfx.base.models.sambanova_constants import SAMBANOVA_MODEL_NAMES
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import DropdownInput, IntInput, SecretStrInput, SliderInput, StrInput
from pydantic.v1 import SecretStr

DEFAULT_SAMBANOVA_API_BASE = "https://api.sambanova.ai/v1"


class SambaNovaComponent(LCModelComponent):
    display_name = "SambaNova"
    description = "Generate text using Sambanova LLMs."
    documentation = "https://cloud.sambanova.ai/"
    icon = "SambaNova"
    name = "SambaNovaModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        StrInput(
            name="base_url",
            display_name="SambaNova Cloud Base Url",
            advanced=True,
            info="The base URL of the Sambanova Cloud API. "
            "Defaults to https://api.sambanova.ai/v1. "
            "You can change this to use other urls like Sambastudio",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=SAMBANOVA_MODEL_NAMES,
            value=SAMBANOVA_MODEL_NAMES[0],
        ),
        SecretStrInput(
            name="api_key",
            display_name="Sambanova API Key",
            info="The Sambanova API Key to use for the Sambanova model.",
            advanced=False,
            value="SAMBANOVA_API_KEY",
            required=True,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            value=2048,
            info="The maximum number of tokens to generate.",
        ),
        SliderInput(
            name="top_p",
            display_name="top_p",
            advanced=True,
            value=1.0,
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            info="Model top_p",
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            advanced=True,
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        sambanova_url = (
            self.base_url
            or os.getenv("SAMBANOVA_API_BASE")
            or os.getenv("SAMBA_NOVA_BASE_URL")
            or DEFAULT_SAMBANOVA_API_BASE
        )

        # Saved flows may carry the full completion URL documented by the old SDK.
        completion_suffix = "/chat/completions"
        normalized_url = sambanova_url.rstrip("/")
        if normalized_url.endswith(completion_suffix):
            sambanova_url = normalized_url[: -len(completion_suffix)]

        sambanova_api_key = self.api_key
        model_name = self.model_name
        max_tokens = self.max_tokens
        top_p = self.top_p
        temperature = self.temperature

        api_key = SecretStr(sambanova_api_key).get_secret_value() if sambanova_api_key else None

        ensure_credential_endpoint_allowed(
            api_key, sambanova_url, default_url=DEFAULT_SAMBANOVA_API_BASE, sdk_env_fallback="SAMBANOVA_API_KEY"
        )
        # SambaNova also loads a separate x-api-key from the environment, even when
        # the tenant supplies the bearer key explicitly.
        ensure_credential_endpoint_allowed(
            None, sambanova_url, default_url=DEFAULT_SAMBANOVA_API_BASE, sdk_env_fallback="SAMBANOVA_API_KEY"
        )

        return ChatSambaNova(
            model=model_name,
            max_tokens=max_tokens or 1024,
            temperature=temperature or 0.07,
            top_p=top_p,
            base_url=sambanova_url,
            sambanova_api_key=api_key,
            **openai_compatible_client_kwargs(sambanova_url, default_url=DEFAULT_SAMBANOVA_API_BASE),
        )
