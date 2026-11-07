"""Generate text with a GenMagic language model."""

from typing import Any

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.io import DropdownInput, FloatInput, IntInput, SecretStrInput

from lfx_bundles.genmagic.genmagic_common import (
    API_BASE_URL,
    API_KEY_INFO,
    API_KEY_VARIABLE,
    API_PREFIX,
    DOCUMENTATION_URL,
    GenMagicAPIError,
    client_header,
    optional_positive_int,
    refresh_model_dropdown,
    require_api_key,
    text_value,
)


class GenMagicModelComponent(LCModelComponent):
    """A chat model on GenMagic's OpenAI-compatible endpoint, for the Agent and other model inputs."""

    display_name = "GenMagic"
    description = "Generate text with any of GenMagic's text models through its OpenAI-compatible API."
    documentation = DOCUMENTATION_URL
    icon = "GenMagic"
    name = "GenMagicModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(
            name="api_key",
            display_name="GenMagic API Key",
            info=API_KEY_INFO,
            value=API_KEY_VARIABLE,
            required=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="The text model. The list loads from the live GenMagic catalog; "
            "type a model ID to use one that is not listed.",
            options=[],
            value="",
            combobox=True,
            refresh_button=True,
            required=True,
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            info="Optional. Leave empty to use the model's own default; some reasoning models do not accept one.",
            advanced=True,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            info="The maximum number of tokens to generate. Leave at 0 for the model's default.",
            value=0,
            advanced=True,
        ),
    ]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Load the text models from the live GenMagic catalog (a public endpoint that needs no key)."""
        if field_name not in {None, "model_name"}:
            return build_config
        return refresh_model_dropdown(build_config, "model_name", "text", include_auto=False)

    def build_model(self) -> LanguageModel:
        """Build a ``ChatOpenAI`` client pointed at GenMagic."""
        from langchain_openai import ChatOpenAI

        # Always pass the key: with ``api_key=None`` the SDK would fall back to OPENAI_API_KEY from the server.
        api_key = require_api_key(self.api_key)
        model_name = text_value(self.model_name)
        if not model_name:
            msg = "Select a GenMagic model."
            raise GenMagicAPIError(msg)
        kwargs: dict[str, Any] = {
            "model": model_name,
            "api_key": api_key,
            "base_url": f"{API_BASE_URL}{API_PREFIX}",
            "default_headers": {"X-GenMagic-Client": client_header()},
            "streaming": bool(self.stream),
        }
        if self.temperature not in {None, ""}:
            kwargs["temperature"] = float(self.temperature)
        if max_tokens := optional_positive_int(self.max_tokens):
            kwargs["max_tokens"] = max_tokens
        return ChatOpenAI(**kwargs)
