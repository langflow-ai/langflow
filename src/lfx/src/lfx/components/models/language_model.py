from lfx.base.models.model import LCModelComponent
from lfx.base.models.unified_models import get_api_key_for_provider, get_language_model_options, get_model_classes
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput
from lfx.io import MessageInput, ModelInput, MultilineInput, SecretStrInput, SliderInput

# Compute model options once at module level
_MODEL_OPTIONS = get_language_model_options()
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
            options=_MODEL_OPTIONS,
            providers=_PROVIDERS,
            info="Select your model provider",
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Model Provider API key",
            real_time_refresh=True,
            advanced=True,
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
        # Safely extract model configuration
        if not self.model or not isinstance(self.model, list) or len(self.model) == 0:
            msg = "A model selection is required"
            raise ValueError(msg)

        model = self.model[0]
        temperature = self.temperature
        stream = self.stream

        # Extract model configuration from metadata
        model_name = model.get("name")
        provider = model.get("provider")
        metadata = model.get("metadata", {})

        # Get model class and parameter names from metadata
        api_key_param = metadata.get("api_key_param", "api_key")

        # Get API key from user input or global variables
        api_key = get_api_key_for_provider(self.user_id, provider, self.api_key)

        # Validate API key (Ollama doesn't require one)
        if not api_key and provider != "Ollama":
            msg = (
                f"{provider} API key is required when using {provider} provider. "
                f"Please provide it in the component or configure it globally as "
                f"{provider.upper().replace(' ', '_')}_API_KEY."
            )
            raise ValueError(msg)

        # Get model class from metadata
        model_class = get_model_classes().get(metadata.get("model_class"))
        if model_class is None:
            msg = f"No model class defined for {model_name}"
            raise ValueError(msg)
        model_name_param = metadata.get("model_name_param", "model")

        # Check if this is a reasoning model that doesn't support temperature
        reasoning_models = metadata.get("reasoning_models", [])
        if model_name in reasoning_models:
            temperature = None

        # Build kwargs dynamically
        kwargs = {
            model_name_param: model_name,
            "streaming": stream,
            api_key_param: api_key,
        }

        if temperature is not None:
            kwargs["temperature"] = temperature

        return model_class(**kwargs)
