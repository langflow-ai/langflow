from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs.inputs import ModelInput
from langflow.io import MessageInput, MultilineInput, SecretStrInput, SliderInput
from langflow.schema.dotdict import dotdict


class UnifiedModelComponent(LCModelComponent):
    display_name = "Unified Model"
    description = "A unified model component that supports both OpenAI and Anthropic models using the new ModelInput."
    documentation: str = "https://docs.langflow.org/components-models"
    icon = "brain-circuit"
    category = "models"
    priority = 1

    inputs = [
        ModelInput(
            name="model_selection",
            display_name="Model",
            info="Select the model to use",
            model_type="language",
            value="OpenAI:gpt-4o",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="The API key for the selected provider",
            required=False,
            real_time_refresh=True,
        ),
        MessageInput(
            name="input_value",
            display_name="Input",
            info="The input text to send to the model",
        ),
        MultilineInput(
            name="system_message",
            display_name="System Message",
            info="The system message to send to the model",
            advanced=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            info="Controls randomness in the model's output",
            value=0.1,
            range_spec={"min": 0, "max": 2, "step": 0.1},
        ),
        SliderInput(
            name="max_tokens",
            display_name="Max Tokens",
            info="The maximum number of tokens to generate",
            value=256,
            range_spec={"min": 1, "max": 128000, "step": 1},
        ),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update the build configuration based on field changes."""
        if field_name == "model_selection" and isinstance(field_value, str) and ":" in field_value:
            # Parse Provider:ModelName format
            provider = field_value.split(":", 1)[0].strip()

            # Update API key display name based on provider
            if provider == "OpenAI":
                build_config["api_key"]["display_name"] = "OpenAI API Key"
                build_config["api_key"]["info"] = "Your OpenAI API key"
            elif provider == "Anthropic":
                build_config["api_key"]["display_name"] = "Anthropic API Key"
                build_config["api_key"]["info"] = "Your Anthropic API key"
            else:
                build_config["api_key"]["display_name"] = "API Key"
                build_config["api_key"]["info"] = "The API key for the selected provider"

        return build_config

    def build_model(self) -> LanguageModel:
        """Build the language model based on the selected provider and configuration."""
        model_selection = self.model_selection

        if not isinstance(model_selection, str):
            msg = "Model selection must be a string in 'Provider:ModelName' format"
            raise TypeError(msg)

        if not model_selection or ":" not in model_selection:
            msg = "Model selection must be in 'Provider:ModelName' format"
            raise ValueError(msg)

        # Parse the selection
        provider, model_name = model_selection.split(":", 1)
        provider = provider.strip()
        model_name = model_name.strip()

        if not provider or not model_name:
            msg = "Both provider and model name must be specified"
            raise ValueError(msg)

        # Build model based on provider
        if provider == "OpenAI":
            return ChatOpenAI(
                openai_api_key=self.api_key,
                model_name=model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        if provider == "Anthropic":
            return ChatAnthropic(
                anthropic_api_key=self.api_key,
                model=model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

        msg = f"Unsupported provider: {provider}. Supported providers: OpenAI, Anthropic"
        raise ValueError(msg)
