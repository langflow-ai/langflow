from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS
from lfx.base.models.model import LCModelComponent
from lfx.base.models.openai_constants import OPENAI_CHAT_MODEL_NAMES
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import DropdownInput, SecretStrInput, SliderInput
from lfx.schema.dotdict import dotdict
from lfx.template.field.base import Output


class ModelsProviderSetupComponent(LCModelComponent):
    """Example component showing how to setup and configure model providers with API keys."""

    display_name = "Models Provider Setup"
    description = "Configure and setup language models from different providers with API key management."
    documentation: str = "https://docs.langflow.org/components-models"
    icon = "brain-circuit"
    category = "models"
    priority = 100

    inputs = [
        DropdownInput(
            name="provider",
            display_name="Model Provider",
            options=["OpenAI", "Anthropic"],
            value="OpenAI",
            info="Select the model provider",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            options=OPENAI_CHAT_MODEL_NAMES,
            value=OPENAI_CHAT_MODEL_NAMES[0],
            info="Select the model to use",
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Model Provider API key (stored securely)",
            required=True,
            value="OPENAI_API_KEY",
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            info="Controls randomness: 0.0 = focused and deterministic, 1.0 = creative and varied",
            range_spec=RangeSpec(min=0, max=1, step=0.1),
        ),
        SliderInput(
            name="max_tokens",
            display_name="Max Tokens",
            value=1000,
            info="Maximum number of tokens to generate",
            range_spec=RangeSpec(min=1, max=4096, step=1),
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Language Model",
            name="model_output",
            method="build_model",
        ),
    ]

    def build_model(self) -> LanguageModel:
        """Build and return the language model using the selected provider and API key."""
        if not self.api_key:
            msg = f"{self.provider} API key is required"
            raise ValueError(msg)

        provider = self.provider
        model_name = self.model_name
        temperature = self.temperature

        if provider == "OpenAI":
            return ChatOpenAI(
                model=model_name,
                api_key=self.api_key,
                temperature=temperature,
                max_tokens=self.max_tokens,
            )
        if provider == "Anthropic":
            return ChatAnthropic(
                model=model_name,
                api_key=self.api_key,
                temperature=temperature,
                max_tokens=self.max_tokens,
            )
        msg = f"Unsupported provider: {provider}"
        raise ValueError(msg)

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update the build configuration dynamically based on field changes."""
        # Update model options and API key label based on selected provider
        if field_name == "provider":
            if field_value == "OpenAI":
                build_config["model_name"]["options"] = OPENAI_CHAT_MODEL_NAMES
                build_config["model_name"]["value"] = OPENAI_CHAT_MODEL_NAMES[0]
                build_config["api_key"]["display_name"] = "OpenAI API Key"
                build_config["api_key"]["value"] = "OPENAI_API_KEY"
            elif field_value == "Anthropic":
                build_config["model_name"]["options"] = ANTHROPIC_MODELS
                build_config["model_name"]["value"] = ANTHROPIC_MODELS[0]
                build_config["api_key"]["display_name"] = "Anthropic API Key"
                build_config["api_key"]["value"] = "ANTHROPIC_API_KEY"

        return build_config
