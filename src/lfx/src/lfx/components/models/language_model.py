from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS
from lfx.base.models.google_generative_ai_constants import GOOGLE_GENERATIVE_AI_MODELS
from lfx.base.models.google_generative_ai_model import ChatGoogleGenerativeAIFixed
from lfx.base.models.model import LCModelComponent
from lfx.base.models.openai_constants import OPENAI_CHAT_MODEL_NAMES, OPENAI_REASONING_MODEL_NAMES
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput
from lfx.io import MessageInput, ModelInput, MultilineInput, SecretStrInput, SliderInput

# Mapping of class names to actual class objects
MODEL_CLASSES = {
    "ChatOpenAI": ChatOpenAI,
    "ChatAnthropic": ChatAnthropic,
    "ChatGoogleGenerativeAIFixed": ChatGoogleGenerativeAIFixed,
}

def _get_language_model_options() -> list[dict[str, Any]]:
    """Return a list of available model providers with their configuration."""
    # OpenAI models
    openai_options = [
        {
            "name": model_name,
            "icon": "OpenAI",
            "category": "OpenAI",
            "provider": "OpenAI",
            "metadata": {
                "context_length": 128000,  # Default, can be model-specific if needed
                "model_class": "ChatOpenAI",
                "model_name_param": "model_name",
                "api_key_param": "openai_api_key",
                "reasoning_models": OPENAI_REASONING_MODEL_NAMES,
            }
        }
        for model_name in OPENAI_CHAT_MODEL_NAMES
    ]

    # Anthropic models
    anthropic_options = [
        {
            "name": model_name,
            "icon": "Anthropic",
            "category": "Anthropic",
            "provider": "Anthropic",
            "metadata": {
                "context_length": 200000,  # Default for Anthropic
                "model_class": "ChatAnthropic",
                "model_name_param": "model",
                "api_key_param": "anthropic_api_key",
            }
        }
        for model_name in ANTHROPIC_MODELS
    ]

    # Google models
    google_options = [
        {
            "name": model_name,
            "icon": "GoogleGenerativeAI",
            "category": "Google",
            "provider": "Google",
            "metadata": {
                "context_length": 32768,  # Default for Google
                "model_class": "ChatGoogleGenerativeAIFixed",
                "model_name_param": "model",
                "api_key_param": "google_api_key",
            }
        }
        for model_name in GOOGLE_GENERATIVE_AI_MODELS
    ]

    return openai_options + anthropic_options + google_options


# Compute model options once at module level
_MODEL_OPTIONS = _get_language_model_options()
_PROVIDERS = [provider["provider"] for provider in _MODEL_OPTIONS]


class LanguageModelComponent(LCModelComponent):
    display_name = "Language Model"
    description = "Runs a language model given a specified provider."
    documentation: str = "https://docs.langflow.org/components-models"
    icon = "brain-circuit"
    category = "models"
    priority = 0  # Set priority to 0 to make it appear first

    inputs = [
        ModelInput(
            name="model",
            display_name="Language Model",
            model_options=_MODEL_OPTIONS,
            providers=_PROVIDERS,
            info="Select your model provider",
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
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

        # Extract model configuration from metadata
        model_name = model.get("name")
        provider = model.get("provider")
        metadata = model.get("metadata", {})

        # Validate API key
        # TODO: We will read this globally soon...
        if not self.api_key:
            msg = f"{provider} API key is required when using {provider} provider"
            raise ValueError(msg)

        # Get model class and parameter names from metadata
        model_class = MODEL_CLASSES[metadata.get("model_class")]
        if not model_class:
            msg = f"No model class defined for {model_name}"
            raise ValueError(msg)

        model_name_param = metadata.get("model_name_param", "model")
        api_key_param = metadata.get("api_key_param", "api_key")

        # Check if this is a reasoning model that doesn't support temperature
        reasoning_models = metadata.get("reasoning_models", [])
        if model_name in reasoning_models:
            temperature = None

        # Build kwargs dynamically
        kwargs = {
            model_name_param: model_name,
            "streaming": stream,
            api_key_param: self.api_key,
        }

        if temperature is not None:
            kwargs["temperature"] = temperature

        return model_class(**kwargs)
