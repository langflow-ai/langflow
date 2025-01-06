from pydantic.v1 import SecretStr

from langflow.base.models.anthropic_constants import ANTHROPIC_MODELS
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.io import DropdownInput, FloatInput, IntInput, MessageTextInput, SecretStrInput


class AnthropicModelComponent(LCModelComponent):
    display_name = "Anthropic"
    description = "Generate text using Anthropic Chat&Completion LLMs with prefill support."
    icon = "Anthropic"
    name = "AnthropicModel"

    inputs = [
        *LCModelComponent._base_inputs,
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            value=4096,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        DropdownInput(
            name="model",
            display_name="Model Name",
            options=ANTHROPIC_MODELS,
            info="https://python.langchain.com/docs/integrations/chat/anthropic",
            value="claude-3-5-sonnet-latest",
        ),
        SecretStrInput(name="anthropic_api_key", display_name="Anthropic API Key", info="Your Anthropic API key."),
        FloatInput(name="temperature", display_name="Temperature", value=0.1),
        MessageTextInput(
            name="anthropic_api_url",
            display_name="Anthropic API URL",
            advanced=True,
            info="Endpoint of the Anthropic API. Defaults to 'https://api.anthropic.com' if not specified.",
        ),
        MessageTextInput(
            name="prefill", display_name="Prefill", info="Prefill text to guide the model's response.", advanced=True
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        try:
            from langchain_anthropic.chat_models import ChatAnthropic
        except ImportError as e:
            msg = "langchain_anthropic is not installed. Please install it with `pip install langchain_anthropic`."
            raise ImportError(msg) from e
        model = self.model
        anthropic_api_key = self.anthropic_api_key
        max_tokens = self.max_tokens
        temperature = self.temperature
        anthropic_api_url = self.anthropic_api_url or "https://api.anthropic.com"

        try:
            output = ChatAnthropic(
                model=model,
                anthropic_api_key=(SecretStr(anthropic_api_key).get_secret_value() if anthropic_api_key else None),
                max_tokens_to_sample=max_tokens,
                temperature=temperature,
                anthropic_api_url=anthropic_api_url,
                streaming=self.stream,
            )
        except Exception as e:
            msg = "Could not connect to Anthropic API."
            raise ValueError(msg) from e

        return output

    def _get_exception_message(self, exception: Exception) -> str | None:
        """Get a message from an Anthropic exception.

        Args:
            exception (Exception): The exception to get the message from.

        Returns:
            str: The message from the exception.
        """
        try:
            from anthropic import BadRequestError
        except ImportError:
            return None
        if isinstance(exception, BadRequestError):
            message = exception.body.get("error", {}).get("message")
            if message:
                return message
        return None
