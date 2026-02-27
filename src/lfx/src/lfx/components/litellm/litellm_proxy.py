import httpx
from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import IntInput, SecretStrInput, SliderInput, StrInput


class LiteLLMProxyComponent(LCModelComponent):
    """LiteLLM Proxy component for routing to multiple LLM providers."""

    display_name = "LiteLLM Proxy"
    description = "Generate text using any LLM provider via a LiteLLM proxy with virtual key authentication."
    icon = "LiteLLM"
    name = "LiteLLMProxyModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        StrInput(
            name="api_base",
            display_name="LiteLLM Proxy URL",
            value="http://localhost:4000/v1",
            required=True,
            info="Base URL of the LiteLLM proxy.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="Virtual Key",
            value="LITELLM_API_KEY",
            required=True,
            info="Virtual key for authentication.",
        ),
        StrInput(
            name="model_name",
            display_name="Model Name",
            required=True,
            info="Model name to use (e.g. gpt-4o, claude-3-opus).",
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
            info="Controls randomness. Lower values are more deterministic.",
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="Maximum number of tokens to generate. Set to 0 for no limit.",
            range_spec=RangeSpec(min=0, max=128000),
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            value=60,
            advanced=True,
            info="Request timeout in seconds.",
        ),
        IntInput(
            name="max_retries",
            display_name="Max Retries",
            value=2,
            advanced=True,
            info="Maximum number of retries on failure.",
        ),
    ]

    def build_model(self) -> LanguageModel:
        """Build the LiteLLM proxy model."""
        api_key = self.api_key
        if isinstance(api_key, SecretStr):
            api_key = api_key.get_secret_value()

        self._validate_proxy_connection(api_key)

        return ChatOpenAI(
            base_url=self.api_base,
            api_key=api_key,
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens if self.max_tokens != 0 else None,
            timeout=self.timeout,
            max_retries=self.max_retries,
            streaming=self.stream,
        )

    def _validate_proxy_connection(self, api_key: str) -> None:
        """Validate the proxy connection, API key, and model availability."""
        base_url = self.api_base.rstrip("/")
        models_url = f"{base_url}/models"

        try:
            response = httpx.get(
                models_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
        except httpx.ConnectError as e:
            msg = (
                f"Could not connect to LiteLLM Proxy at {base_url}. Verify the URL is correct and the proxy is running."
            )
            raise ValueError(msg) from e
        except httpx.TimeoutException as e:
            msg = f"Connection to LiteLLM Proxy at {base_url} timed out."
            raise ValueError(msg) from e

        http_unauthorized = 401
        if response.status_code == http_unauthorized:
            msg = "Authentication failed. Check that your Virtual Key is valid and not expired."
            raise ValueError(msg)

        response.raise_for_status()

        data = response.json()
        available_models = [m.get("id", "") for m in data.get("data", [])]
        if available_models and self.model_name not in available_models:
            msg = (
                f"Model '{self.model_name}' not found on the LiteLLM Proxy. "
                f"Available models: {', '.join(available_models)}"
            )
            raise ValueError(msg)

    def _get_exception_message(self, e: Exception) -> str | None:
        """Extract meaningful error messages from OpenAI client exceptions."""
        try:
            from openai import AuthenticationError, BadRequestError, NotFoundError
        except ImportError:
            return None

        if isinstance(e, AuthenticationError):
            return "Authentication failed. Check that your Virtual Key is valid and not expired."
        if isinstance(e, NotFoundError):
            return f"Model '{self.model_name}' not found. Verify the model name."
        if isinstance(e, BadRequestError):
            message = e.body.get("message") if isinstance(e.body, dict) else None
            if message:
                return message
        return None
