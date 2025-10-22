from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from lfx.base.models.google_generative_ai_model import ChatGoogleGenerativeAIFixed
from lfx.base.models.model import LCModelComponent
from lfx.base.models.openai_constants import OPENAI_REASONING_MODEL_NAMES
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput
from lfx.io import MessageInput, ModelInput, MultilineInput, SecretStrInput, SliderInput


class LanguageModelComponent(LCModelComponent):
    display_name = "Language Model"
    description = "Runs a language model given a specified provider."
    documentation: str = "https://docs.langflow.org/components-models"
    icon = "brain-circuit"
    category = "models"
    priority = 0  # Set priority to 0 to make it appear first

    @staticmethod
    def get_model_options() -> list[dict[str, Any]]:
        """Return a list of available model providers."""
        # TODO: Use the CRUD endpoints to fetch available providers dynamically
        return [
            {
                "name": "gpt-4",
                "icon": "OpenAI",
                "category": "OpenAI",
                "provider": "OpenAI",
                "metadata": {"context_length": 8192},
            },
            {
                "name": "claude-3-opus",
                "icon": "Anthropic",
                "category": "Anthropic",
                "provider": "Anthropic",
                "metadata": {"context_length": 200000},
            },
            {
                "name": "gemini-pro",
                "icon": "GoogleGenerativeAI",
                "category": "Google",
                "provider": "Google",
                "metadata": {"context_length": 32768},
            },
        ]

    inputs = [
        ModelInput(
            name="model",
            display_name="Language Model",
            model_options=get_model_options(),
            providers=[provider["provider"] for provider in get_model_options()],
            info="Select your model provider",
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="OpenAI API Key",
            info="Model Provider API key",
            required=False,
            show=True,
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
            info="A system message that helps set the behavior of the assistant",
            advanced=False,
        ),
        BoolInput(
            name="stream",
            display_name="Stream",
            info="Whether to stream the response",
            value=False,
            advanced=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            info="Controls randomness in responses",
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
        ),
    ]

    def build_model(self) -> LanguageModel:
        model = self.model[0]
        temperature = self.temperature
        stream = self.stream

        # Extract the provider and model name
        provider = model.get("provider")
        model_name = model.get("name")

        if provider == "OpenAI":
            if not self.api_key:
                msg = "OpenAI API key is required when using OpenAI provider"
                raise ValueError(msg)

            if model_name in OPENAI_REASONING_MODEL_NAMES:
                # reasoning models do not support temperature (yet)
                temperature = None

            return ChatOpenAI(
                model_name=model_name,
                temperature=temperature,
                streaming=stream,
                openai_api_key=self.api_key,
            )
        if provider == "Anthropic":
            if not self.api_key:
                msg = "Anthropic API key is required when using Anthropic provider"
                raise ValueError(msg)
            return ChatAnthropic(
                model=model_name,
                temperature=temperature,
                streaming=stream,
                anthropic_api_key=self.api_key,
            )
        if provider == "Google":
            if not self.api_key:
                msg = "Google API key is required when using Google provider"
                raise ValueError(msg)
            return ChatGoogleGenerativeAIFixed(
                model=model_name,
                temperature=temperature,
                streaming=stream,
                google_api_key=self.api_key,
            )
        msg = f"Unknown provider: {provider}"
        raise ValueError(msg)
